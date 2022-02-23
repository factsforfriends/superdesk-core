# -*- coding: utf-8; -*-
#
# This file extends Superdesk.
#
# Copyright 2022 Facts for Friends GmbH and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import json
import logging
import datetime

from copy import deepcopy
from superdesk.io.registry import register_feed_parser
from superdesk.io.feed_parsers import FeedParser
from superdesk.metadata.utils import generate_tag_from_url

logger = logging.getLogger(__name__)


class FactSnackFeedParser(FeedParser):
    """
    A custom parser for dicts used by Facts for Friends
    """

    NAME = "f3parser"

    label = "Fact Snack Parser"

    required_properties = (
        "language",
        "headline",
        "claim",
        "fact"
    )

    def __init__(self):
        super().__init__()

    def can_parse(self, item):
        try:
            return isinstance(item, dict) and set(self.required_properties).issubset(item.keys())
        except AttributeError:
            return False

    def parse(self, item, provider=None):
        guid = item.get("guid")
        if not guid and item.get("url"):
            guid = generate_tag_from_url(item["url"], "urn")
        new_item = {"guid": guid, "type": item.get("type", "text"), "url": item.get("url"), "profile": "Fact Snack"}

        new_item["language"] = item.get("language")
        new_item["headline"] = item.get("headline")
        new_item["original_source"] = item.get("source", "")
        new_item["priority"] = int(item.get("priority", "5"))

        new_item["extra"] = {
            "factsnack-claim": item.get("claim"),
            "factsnack-fact": item.get("fact"),
            "factsnack-source": item.get("url")
        }
        return item

register_feed_parser(FactSnackFeedParser.NAME, FactSnackFeedParser())
