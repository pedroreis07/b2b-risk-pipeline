from datetime import datetime
from zoneinfo import ZoneInfo

from dateutil.relativedelta import relativedelta


def calc_company_age(date_string: str) -> float:
    tz = ZoneInfo("America/Sao_Paulo")
    target_date = datetime.strptime(date_string, "%Y-%m-%d").replace(tzinfo=tz)
    now = datetime.now(tz)
    delta = relativedelta(now, target_date)
    return round(delta.years + delta.months / 12, 1)
