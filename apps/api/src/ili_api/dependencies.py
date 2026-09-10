from fastapi import Request

from ili_api.services.steam import SteamInspectionService


def get_steam_service(request: Request) -> SteamInspectionService:
    return request.app.state.steam_service
