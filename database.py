"""SQLite baza podataka za TCG karte (SQLAlchemy)."""

from __future__ import annotations

import shutil
from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from config import DATABASE_PATH, DATABASE_URL, SEED_DATABASE_PATH


class Base(DeclarativeBase):
    pass


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    supertype: Mapped[str | None] = mapped_column(String, nullable=True)
    rarity: Mapped[str | None] = mapped_column(String, nullable=True)
    set_name: Mapped[str | None] = mapped_column(String, nullable=True)
    market_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pokewallet_id: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
    )
    portfolio_lots: Mapped[list["Portfolio"]] = relationship(
        back_populates="card",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Card id={self.id!r} name={self.name!r} price={self.market_price}>"


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    card: Mapped[Card] = relationship(back_populates="price_history")

    def __repr__(self) -> str:
        return f"<PriceHistory card_id={self.card_id!r} date={self.date} price={self.price}>"


class Portfolio(Base):
    __tablename__ = "portfolio"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    card_id: Mapped[str] = mapped_column(ForeignKey("cards.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[float] = mapped_column(Float, nullable=False)
    purchase_date: Mapped[str] = mapped_column(String, nullable=False)

    card: Mapped[Card] = relationship(back_populates="portfolio_lots")

    def __repr__(self) -> str:
        return (
            f"<Portfolio id={self.id} card_id={self.card_id!r} "
            f"qty={self.quantity} price={self.purchase_price}>"
        )


engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _ensure_card_columns() -> None:
    """SQLite ne dodaje nove stupce kroz create_all na postojećoj tablici."""
    if not inspect(engine).has_table("cards"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("cards")}
    with engine.begin() as connection:
        if "pokewallet_id" not in columns:
            connection.execute(text("ALTER TABLE cards ADD COLUMN pokewallet_id VARCHAR"))
        if "image_url" not in columns:
            connection.execute(text("ALTER TABLE cards ADD COLUMN image_url VARCHAR"))


def _backfill_image_urls() -> None:
    """Postojećim kartama bez image_url dodaje CDN link s images.pokemontcg.io."""
    if not inspect(engine).has_table("cards"):
        return
    columns = {column["name"] for column in inspect(engine).get_columns("cards")}
    if "image_url" not in columns:
        return
    with engine.begin() as connection:
        rows = connection.execute(
            text("SELECT id FROM cards WHERE image_url IS NULL OR image_url = ''")
        ).fetchall()
        for (card_id,) in rows:
            if "-" not in str(card_id):
                continue
            set_code, number = str(card_id).rsplit("-", 1)
            url = f"https://images.pokemontcg.io/{set_code}/{number}.png"
            connection.execute(
                text("UPDATE cards SET image_url = :url WHERE id = :card_id"),
                {"url": url, "card_id": card_id},
            )


def init_db() -> None:
    """Kreira tablice cards, price_history i portfolio ako ne postoje."""
    Base.metadata.create_all(bind=engine)
    _ensure_card_columns()
    _backfill_image_urls()


def _price_history_count() -> int:
    if not inspect(engine).has_table("price_history"):
        return 0
    with engine.connect() as connection:
        return int(connection.execute(text("SELECT COUNT(*) FROM price_history")).scalar() or 0)


def ensure_seed_database() -> bool:
    """Ako je price_history prazna, kopiraj seed bazu (za Streamlit Cloud / prvi start).

    Vraća True ako je seed primijenjen.
    """
    init_db()
    if _price_history_count() > 0:
        return False
    if not SEED_DATABASE_PATH.is_file():
        return False

    engine.dispose()
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SEED_DATABASE_PATH, DATABASE_PATH)
    init_db()
    return _price_history_count() > 0


def get_session() -> Session:
    return SessionLocal()


def add_portfolio_position(
    card_id: str,
    quantity: int,
    purchase_price: float,
    purchase_date: str | None = None,
) -> None:
    """Sprema jednu nabavu u portfolio. Datum je ISO string (YYYY-MM-DD)."""
    if int(quantity) < 1:
        raise ValueError("Količina mora biti barem 1.")
    if float(purchase_price) <= 0:
        raise ValueError("Nabavna cijena mora biti veća od nule.")
    with SessionLocal() as session:
        session.add(
            Portfolio(
                card_id=card_id,
                quantity=int(quantity),
                purchase_price=float(purchase_price),
                purchase_date=purchase_date or date.today().isoformat(),
            )
        )
        session.commit()


def delete_portfolio_position(entry_id: int) -> bool:
    """Briše jedan unos: DELETE FROM portfolio WHERE id = ?"""
    with SessionLocal() as session:
        result = session.execute(
            text("DELETE FROM portfolio WHERE id = :entry_id"),
            {"entry_id": int(entry_id)},
        )
        session.commit()
        return bool(result.rowcount)
