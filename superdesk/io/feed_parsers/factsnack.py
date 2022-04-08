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
        "fact",
        "url"
    )

    rating_map = {
        'fehlender kontext': 'misleading',
        'teilweise falsch': 'misleading',
        'falsch': 'refuted', 
        'größtenteils falsch': 'misleading', 
        'frei erfunden': 'refuted', 
        'unbelegt': 'refuted', 
        'falsche überschrift': 'misleading', 
        'manipuliert': 'misleading', 
        'größtenteils richtig': 'misleading', 
        'falscher kontext': 'misleading',
        'belegt': 'verified',
        'richtig': 'verified',
        'wahr': 'verified'
    }

    def __init__(self):
        super().__init__()

    def can_parse(self, item):
        try:
            return isinstance(item, dict) and set(self.required_properties).issubset(item.keys())
        except AttributeError:
            return False

    def _rating(self, s = None):
        if s is not None:
            try:
                return(self.rating_map[s.lower()]) 
            except KeyError:
                logger.warning('Unknown rating: {}'.format(s))
                return("")
        return("")

    def parse(self, item, provider=None):

        guid = item.get("guid")
        if not guid and item.get("url"):
            guid = generate_tag_from_url(item["url"], "urn")
        new_item = {"guid": guid, "type": item.get("type", "text"), "url": item.get("url"), "profile": "Fact Snack", "version": 1}

        new_item["slugline"] = item.get("slugline", "")
        new_item["language"] = item.get("language")
        new_item["headline"] = item.get("headline")
        new_item["original_source"] = item.get("url")
        new_item["priority"] = int(item.get("priority", "3"))

        new_item["rating"] = self._rating(item.get("rating", None))

        new_item["extra"] = {
            "factsnack-claim": item.get("claim"),
            "factsnack-fact": item.get("fact"),
            "factsnack-source": item.get("url")
        }

        date = item.get("date", "")
        if date != "":
            new_item["versioncreated"] = datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M")
        else:
            new_item["versioncreated"] = datetime.datetime.now()
        return [new_item]

register_feed_parser(FactSnackFeedParser.NAME, FactSnackFeedParser())
