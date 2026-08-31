"""Endpoint registry — extracted from j7/c.java (RequestConfigUrlType.kt).

These are the v3 `/m/v%s/command` names. Only some are usable without a logged-in
session; the rest are kept so the payload shapes can be completed incrementally.
"""

COMMANDS = {
    # app detail + versions (proven 200, tested)
    "get_app_detail": {
        "desc": "Full app detail incl. asset.url (XAPK) + file_sha256",
        "params": {"packageName": str, "page": str, "hl": str},
    },
    "get_app_his_version": {
        "desc": "Version history for a package",
        "params": {"packageName": str},
    },
    "get_app_developer": {
        "desc": "Apps by developer",
        "params": {"developerId": str},
    },
    "get_app_similar": {
        "desc": "Similar app suggestions",
        "params": {"packageName": str},
    },
    "get_app_recommend": {
        "desc": "Recommended apps",
        "params": {"packageName": str},
    },
    "get_app_list_about_tag": {
        "desc": "Apps for a tag",
        "params": {"tagId": str},
    },
    # search & catalogue
    "search_query": {"desc": "Search apps", "params": {"q": str}},
    "search_user": {"desc": "Search users", "params": {"q": str}},
    "get_top": {"desc": "Top apps", "params": {}},
    "get_top_developer_list": {"desc": "Top developers", "params": {}},
    "get_market_category": {"desc": "Market categories", "params": {}},
    "get_market_rank": {"desc": "Market rank", "params": {}},
    # topics / CMS
    "get_topic_list": {"desc": "Topic list", "params": {}},
    "get_topics": {"desc": "Topics", "params": {}},
    "get_topic_app_banner_list": {"desc": "Topic app banners", "params": {}},
    "get_app_category": {"desc": "App category", "params": {}},
}

# Commands confirmed to answer 200 retcode=0 unauthenticated (tested live).
TESTED = {"get_app_detail", "get_app_his_version"}


def command_names():
    return sorted(COMMANDS)