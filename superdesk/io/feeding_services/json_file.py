# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013-2018 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import re

from datetime import datetime

from superdesk.errors import IngestApiError, ParserError
from superdesk.io.registry import register_feeding_service
from superdesk.io.feeding_services.http_base_service import HTTPFeedingServiceBase

class JSONFileFeedingService(HTTPFeedingServiceBase):
    """
    Feeding Service class for reading JSON files
    """

    NAME = "json_file"
    ERRORS = [ParserError.parseMessageError().get_error_description()]

    label = "JSON file feed"

    fields = [
        {
            "id": "url",
            "type": "text",
            "label": "File URL",
            "placeholder": "File URL",
            "required": True,
            "default": "",
        }
    ]
    HTTP_AUTH = False

    def __init__(self):
        super().__init__()

    def _test(self, provider):
        config = self.config
        url = config["url"]

        self.get_url(url)

    def _update(self, provider, update):
        response = self.get_url(url)
        
        json_items = json.loads(response)
        if not isinstance(json_items, list):
            json_items = [json_items]

        parsed_items = []

        for item in json_items:
            try:
                parser = self.get_feed_parser(provider, item)
                parsed_items.append(parser.parse(item))
            except Exception as ex:
                raise ParserError.parseMessageError(ex, provider, data=item)

        return parsed_items


register_feeding_service(JSONFileFeedingService)
