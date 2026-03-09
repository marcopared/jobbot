from apps.browser.ats.ashby import AshbyHandler
from apps.browser.ats.base import BaseATSHandler
from apps.browser.ats.greenhouse import GreenhouseHandler
from apps.browser.ats.lever import LeverHandler
from apps.browser.ats.workday import WorkdayHandler
from apps.browser.ats.yc import YCHandler
from core.db.models import ATSType


def get_handler(ats_type: ATSType) -> BaseATSHandler:
    if ats_type == ATSType.GREENHOUSE:
        return GreenhouseHandler()
    if ats_type == ATSType.LEVER:
        return LeverHandler()
    if ats_type == ATSType.ASHBY:
        return AshbyHandler()
    if ats_type == ATSType.WORKDAY:
        return WorkdayHandler()
    if ats_type == ATSType.YC:
        return YCHandler()
    return WorkdayHandler()


__all__ = ["get_handler", "BaseATSHandler"]
