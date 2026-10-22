"""SQLite baza podataka za TCG karte (SQLAlchemy)."""

from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from config import DATABASE_URL


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

    price_history: Mapped[list["PriceHistory"]] = relationship(
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


engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def init_db() -> None:
    """Kreira tablice cards i price_history ako ne postoje."""
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
