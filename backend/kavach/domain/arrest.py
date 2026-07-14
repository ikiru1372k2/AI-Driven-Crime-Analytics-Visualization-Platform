"""ArrestSurrender domain entity — exact ER mapping (matrix §1.6).

The referenced junction table `inv_arrestsurrenderaccused` is UNDEFINED in the
source document (matrix §2) and is intentionally NOT implemented — the direct
FK ArrestSurrender.AccusedMasterID is the authoritative accused linkage. No
columns are invented for the undefined junction.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class ArrestSurrender(BaseModel):
    model_config = ConfigDict(frozen=True)

    arrest_surrender_id: int  # PK
    case_master_id: int  # FK CaseMaster
    arrest_surrender_type_id: int | None = None  # lookup: arrest vs surrender
    arrest_surrender_date: date | None = None
    arrest_surrender_state_id: int | None = None  # FK State
    arrest_surrender_district_id: int | None = None  # FK District
    police_station_id: int | None = None  # FK Unit.UnitID
    ioid: int | None = None  # FK Employee.EmployeeID (Investigating Officer)
    court_id: int | None = None  # FK Court
    accused_master_id: int | None = None  # FK Accused.AccusedMasterID
    is_accused: bool | None = None  # BIT: primary accused flag
    is_complainant_accused: bool | None = None  # BIT: complainant also accused
