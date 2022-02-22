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
from superdesk.utc import utc
from superdesk.metadata.utils import generate_tag_from_url

logger = logging.getLogger(__name__)


class F3JSONFeedParser(FeedParser):
    """
    Feed Parser for our JSON files
    """

    NAME = "f3json"

    label = "F3JSON Feed Parser"

    direct_copy_properties = (
        "language",
        "headline",
        "slugline",
    )

    items = []

    def __init__(self):
        super().__init__()

    def can_parse(self, content):
        try:
            articles = json.loads(content)
            return True
        except Exception:
            pass
        return False

    def parse(self, content, provider=None):
        self.items = []
        articles = json.loads(content)
        for article in articles:
            self.items.append(self._transform_from_js(article))
        return self.items

    def _transform_from_js(self, article):
        guid = article.get("guid")
        if not guid and article.get("uri"):
            guid = generate_tag_from_url(article["uri"], "urn")
        item = {"guid": guid, "type": article.get("type", "text"), "uri": article.get("uri"), "profile": "Fact Snack"}

        for copy_property in self.direct_copy_properties:
            if article.get(copy_property) is not None:
                item[copy_property] = article[copy_property]

        item["original_source"] = article.get("source", "")
        item["priority"] = int(article.get("priority", "5"))

        item["extra"] = {
            "factsnack-claim": article.get("claim", ""),
            "factsnack-fact": article.get("fact", ""),
            "factsnack-source": article.get("uri")
        }

        return item

register_feed_parser(F3JSONFeedParser.NAME, F3JSONFeedParser())
