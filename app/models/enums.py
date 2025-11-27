"""
Tekmetric Status Codes and Enums

Standardized constants for TM API values.
Reference: Captured from TM API responses Nov 2025.
"""

from enum import IntEnum, Enum


class ROStatus(IntEnum):
    """Repair Order status codes"""
    ESTIMATE = 1
    WORK_IN_PROGRESS = 2
    WAITING_FOR_PARTS = 3
    WAITING_FOR_APPROVAL = 4
    POSTED = 5
    COMPLETED = 6
    VOID = 7

    @classmethod
    def to_label(cls, status: int) -> str:
        labels = {
            1: "Estimate",
            2: "Work In Progress",
            3: "Waiting for Parts",
            4: "Waiting for Approval",
            5: "Posted",
            6: "Completed",
            7: "Void"
        }
        return labels.get(status, f"Unknown ({status})")


class EmployeeRole(IntEnum):
    """Employee role codes"""
    SHOP_ADMIN = 1
    SERVICE_ADVISOR = 2
    TECHNICIAN = 3
    OWNER = 4
    PARTS_MANAGER = 5

    @classmethod
    def to_label(cls, role: int) -> str:
        labels = {
            1: "Shop Admin",
            2: "Service Advisor",
            3: "Technician",
            4: "Owner",
            5: "Parts Manager"
        }
        return labels.get(role, f"Unknown ({role})")


class InspectionRating(IntEnum):
    """Inspection item ratings"""
    GOOD = 1
    MAY_REQUIRE_ATTENTION = 2
    REQUIRES_ATTENTION = 3

    @classmethod
    def to_label(cls, rating: int) -> str:
        labels = {
            1: "Good",
            2: "May Require Attention",
            3: "Requires Attention"
        }
        return labels.get(rating, f"Unknown ({rating})")


class CustomerType(IntEnum):
    """Customer type codes"""
    PERSON = 1
    BUSINESS = 2


class JobBoard(str, Enum):
    """Job board types"""
    ACTIVE = "ACTIVE"
    POSTED = "POSTED"
    COMPLETE = "COMPLETE"


class FeeType(str, Enum):
    """Fee categories for GP attribution"""
    SHOP_SUPPLIES = "SHOP_SUPPLIES"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    HAZARDOUS_WASTE = "HAZARDOUS_WASTE"
    DISPOSAL = "DISPOSAL"
    OTHER = "OTHER"

    @classmethod
    def from_name(cls, name: str) -> "FeeType":
        """Detect fee type from name string"""
        name_lower = name.lower()
        if "shop" in name_lower and "suppl" in name_lower:
            return cls.SHOP_SUPPLIES
        elif "environ" in name_lower:
            return cls.ENVIRONMENTAL
        elif "hazard" in name_lower or "haz" in name_lower:
            return cls.HAZARDOUS_WASTE
        elif "dispos" in name_lower:
            return cls.DISPOSAL
        return cls.OTHER


class TechRateSource(str, Enum):
    """Source of technician rate used in GP calculation"""
    ASSIGNED = "assigned"           # Tech explicitly assigned to labor
    SHOP_AVERAGE = "shop_average"   # Fallback to shop average
    DEFAULT = "default"             # Fallback to default ($25/hr)


class AuthorizationMethod(str, Enum):
    """Job authorization methods"""
    VERBAL_IN_PERSON = "VERBAL_IN_PERSON"
    VERBAL_BY_PHONE = "VERBAL_BY_PHONE"
    WRITTEN = "WRITTEN"
    ELECTRONIC = "ELECTRONIC"


class PaymentType(IntEnum):
    """Payment type codes"""
    CASH = 1
    CHECK = 2
    CREDIT_CARD = 3
    DEBIT_CARD = 4
    OTHER = 5
    FINANCING = 6

    @classmethod
    def to_label(cls, ptype: int) -> str:
        labels = {
            1: "Cash",
            2: "Check",
            3: "Credit Card",
            4: "Debit Card",
            5: "Other",
            6: "Financing"
        }
        return labels.get(ptype, f"Unknown ({ptype})")
