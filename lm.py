# -----------------------------------------------------------
#  library_service.py   (self‑contained mini‑library backend)
# -----------------------------------------------------------
"""A minimal in‑memory LibraryService implemented in Python 3.

This file is self‑contained: run it directly to see a small demo, or
import the classes into your test suite.  It mirrors the Java design
used earlier but follows Pythonic conventions.
"""
from __future__ import annotations

import datetime as _dt
import decimal as _dec
from dataclasses import dataclass, field
from typing import List, Dict, Optional

_dec.getcontext().prec = 9  # two decimals are enough for money


# ---------------------------------------------------------------------------
# Domain objects
# ---------------------------------------------------------------------------
class Money(_dec.Decimal):
    """Ultra‑light wrapper so we can write Money("5.00") and use arithmetic."""
    def __new__(cls, value="0.00"):
        return super().__new__(cls, str(value))  # always keep two decimals

    def __str__(self):
        return f"{self:.2f} €"


@dataclass(frozen=True)
class Book:
    isbn: str
    title: str
    tags: List[str] = field(default_factory=list)


@dataclass
class BorrowRecord:
    isbn: str
    borrowed_on: _dt.date
    due_on: _dt.date
    returned_on: Optional[_dt.date] = None

    def is_overdue(self, as_of: _dt.date) -> bool:
        return self.returned_on is None and as_of > self.due_on


class MemberStatus:
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


@dataclass
class Member:
    member_id: int
    status: str = MemberStatus.ACTIVE
    _borrowed: Dict[str, BorrowRecord] = field(default_factory=dict, init=False, repr=False)

    def borrow(self, isbn: str, due_on: _dt.date) -> BorrowRecord:
        rec = BorrowRecord(isbn, _dt.date.today(), due_on)
        self._borrowed[isbn] = rec
        return rec

    def return_book(self, isbn: str, when: _dt.date) -> Optional[BorrowRecord]:
        rec = self._borrowed.pop(isbn, None)
        if rec:
            rec.returned_on = when
        return rec

    @property
    def borrowed(self):
        return self._borrowed.values()


class ReceiptStatus:
    BORROWED = "BORROWED"
    RETURNED_ON_TIME = "RETURNED_ON_TIME"
    RETURNED_LATE = "RETURNED_LATE"


@dataclass(frozen=True)
class Receipt:
    status: str
    when: _dt.date
    isbn: str


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------
class MemberBlockedException(Exception):
    pass


class BookNotFoundException(Exception):
    pass


class BookNotBorrowedException(Exception):
    pass


# ---------------------------------------------------------------------------
# Service interface & implementation
# ---------------------------------------------------------------------------
class LibraryService:
    """Logical interface. In Python we rely on duck typing."""
    def borrow_book(self, member: Member, isbn: str, due_date: _dt.date) -> Receipt: ...
    def return_book(self, member: Member, isbn: str, return_date: _dt.date) -> Receipt: ...
    def calculate_fine(self, member: Member, as_of_date: _dt.date) -> Money: ...
    def search_books(self, query: str, tags: List[str], page_size: int, page_number: int) -> List[Book]: ...


class LibraryServiceImpl(LibraryService):
    """A very small in‑memory implementation suitable for unit tests."""
    DAILY_FINE = Money("0.50")

    def __init__(self):
        self.catalogue: Dict[str, Book] = {}
        self.members: Dict[int, Member] = {}

    # ---------------- private helpers ----------------
    def _validate_member(self, member: Member):
        if member is None:
            raise ValueError("member must not be None")
        if member.status == MemberStatus.BLOCKED:
            raise MemberBlockedException("Member is blocked")

    def _get_book(self, isbn: str) -> Book:
        book = self.catalogue.get(isbn)
        if book is None:
            raise BookNotFoundException(f"ISBN {isbn} not found")
        return book

    # ---------------- API implementation -------------
    def borrow_book(self, member: Member, isbn: str, due_date: _dt.date) -> Receipt:
        self._validate_member(member)
        if due_date is None or due_date <= _dt.date.today():
            raise ValueError("due_date must be in the future")
        self._get_book(isbn)  # ensure book exists
        member.borrow(isbn, due_date)
        return Receipt(ReceiptStatus.BORROWED, _dt.date.today(), isbn)

    def return_book(self, member: Member, isbn: str, return_date: _dt.date) -> Receipt:
        self._validate_member(member)
        if return_date is None:
            raise ValueError("return_date must not be None")
        rec = member.return_book(isbn, return_date)
        if rec is None:
            raise BookNotBorrowedException("Book was not borrowed by member")
        status = (ReceiptStatus.RETURNED_LATE if return_date > rec.due_on
                  else ReceiptStatus.RETURNED_ON_TIME)
        return Receipt(status, return_date, isbn)

    def calculate_fine(self, member: Member, as_of_date: _dt.date) -> Money:
        self._validate_member(member)
        if as_of_date is None:
            raise ValueError("as_of_date must not be None")
        total = Money("0.00")
        for br in member.borrowed:
            if br.is_overdue(as_of_date):
                days = (as_of_date - br.due_on).days
                total += self.DAILY_FINE * days
        return total

    def search_books(self, query: str, tags: List[str], page_size: int, page_number: int) -> List[Book]:
        if not query or query.isspace():
            raise ValueError("query must not be empty")
        if tags is None:
            raise ValueError("tags must not be None")
        if not (1 <= page_size <= 100):
            raise ValueError("page_size must be 1..100")
        if page_number < 0:
            raise ValueError("page_number must be >= 0")

        stream = self.catalogue.values()
        if query != "*":
            stream = [b for b in stream if query.lower() in b.title.lower()]
        if tags:
            stream = [b for b in stream if all(t in b.tags for t in tags)]

        start = page_size * page_number
        end   = start + page_size
        return list(stream)[start:end]

    # ---------------- demo / seed data ---------------
    @classmethod
    def demo(cls) -> "LibraryServiceImpl":
        svc = cls()
        # books
        svc.catalogue["978-0132350884"] = Book("978-0132350884", "Clean Code", ["java", "architecture"])
        svc.catalogue["978-0321356680"] = Book("978-0321356680", "Effective Java", ["java"])
        # members
        svc.members[42] = Member(42, MemberStatus.ACTIVE)
        svc.members[77] = Member(77, MemberStatus.BLOCKED)
        svc.members[99] = Member(99, MemberStatus.ACTIVE)
        return svc


# ---------------------------------------------------------------------------
# Quick manual run (python library_service.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    lib = LibraryServiceImpl.demo()
    m    = lib.members[42]

    due = _dt.date.today() + _dt.timedelta(days=14)
    receipt = lib.borrow_book(m, "978-0132350884", due)
    print("Borrowed:", receipt)

    # Fast‑forward 16 days
    later = _dt.date.today() + _dt.timedelta(days=16)
    receipt2 = lib.return_book(m, "978-0132350884", later)
    print("Returned:", receipt2)
    fine = lib.calculate_fine(m, later)
    print("Fine due:", fine)

    print("Search result:", lib.search_books("java", [], 10, 0))
