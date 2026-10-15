"""Modelo canónico del gateway: el vocabulario que ven los consumidores."""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class CompanyRef(BaseModel):
    id: str
    name: str


class Member(BaseModel):
    document: str
    fullName: str
    status: str = Field(description="ACTIVE, RETIRED o SUSPENDED")
    company: Optional[CompanyRef] = None


class Beneficiary(BaseModel):
    document: str
    fullName: str
    relationship: str = Field(description="SPOUSE, CHILD, FATHER o MOTHER")


class Company(BaseModel):
    id: str
    name: str
    activeMembers: int


class RetirementRequest(BaseModel):
    requestId: str = Field(min_length=1, max_length=100)
    date: date
    reason: str = Field(min_length=1, max_length=200)


BeneficiaryList = List[Beneficiary]
