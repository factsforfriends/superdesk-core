# -*- coding: utf-8; -*-
#
# This file is part of Superdesk.
#
# Copyright 2013, 2014 Sourcefabric z.u. and contributors.
#
# For the full copyright and license information, please see the
# AUTHORS and LICENSE files distributed with this source code, or
# at https://www.sourcefabric.org/superdesk/license

import superdesk

from copy import deepcopy
from flask import current_app as app, json, g
from eve_elastic.elastic import set_filters

from superdesk import get_resource_service
from superdesk.metadata.item import CONTENT_STATE, ITEM_STATE, get_schema
from superdesk.metadata.utils import aggregations as common_aggregations, item_url, _set_highlight_query
from apps.archive.archive import SOURCE as ARCHIVE, ArchiveResource, private_content_filter
from superdesk.resource import build_custom_hateoas
from apps.publish.published_item import published_item_fields
from superdesk import es_utils


class SearchService(superdesk.Service):
    """Federated search service.

    It can search against different collections like Ingest, Production, Archived etc.. at the same time.
    """

    repos = None
    aggregations = deepcopy(common_aggregations)

    @property
    def elastic(self):
        return app.data.elastic

    def __init__(self, datasource, backend):
        super().__init__(datasource=datasource, backend=backend)

    def get_ingest_filters(self):
        """
        Returns Ingest filters
        """
        return [{"term": {"_type": "ingest"}}]

    def get_archive_filters(self):
        """
        Returns Archive filters

        If the content state is draft, it must be from the current user
        """
        filters = [deepcopy(ArchiveResource.datasource["elastic_filter"])]
        private_filter = private_content_filter()
        if private_filter:
            filters.append(private_filter)
        return filters

    def get_published_filters(self):
        """
        Returns published filters
        """
        return [
            {"term": {"_type": "published"}},
            {
                "terms": {
                    ITEM_STATE: [
                        CONTENT_STATE.SCHEDULED,
                        CONTENT_STATE.PUBLISHED,
                        CONTENT_STATE.KILLED,
                        CONTENT_STATE.RECALLED,
                        CONTENT_STATE.CORRECTED,
                        CONTENT_STATE.UNPUBLISHED,
                        CONTENT_STATE.BEING_CORRECTED,
                    ]
                }
            },
        ]

    def get_archived_filters(self):
        """
        Returns archived filters
        """
        return [{"term": {"_type": "archived"}}]

    def _get_private_filters(self, repo, invisible_stages):
        query = {"and": []}

        if repo == "ingest":
            query["and"].extend(self.get_ingest_filters())
        elif repo == "archive":
            query["and"].extend(self.get_archive_filters())
        elif repo == "published":
            query["and"].extend(self.get_published_filters())
        elif repo == "archived":
            query["and"].extend(self.get_archived_filters())

        if invisible_stages and repo != "ingest":
            query["and"].append({"not": {"terms": {"task.stage": invisible_stages}}})

        return query

    def _get_query(self, req):
        """Get elastic query."""
        args = getattr(req, "args", {})
        source = json.loads(args.get("source")) if args.get("source") else {"query": {"filtered": {}}}

        try:
            self._enhance_query_string(source["query"]["filtered"]["query"]["query_string"])
        except KeyError:
            pass

        if app.data.elastic.should_aggregate(req):
            source["aggs"] = self.aggregations

        if app.data.elastic.should_highlight(req):
            _set_highlight_query(source)

        return source

    def _enhance_query_string(self, query_string):
        query_string.setdefault("analyze_wildcard", app.config["ELASTIC_QUERY_STRING_ANALYZE_WILDCARD"])

    def _get_projected_fields(self, req):
        """Get elastic projected fields."""
        if app.data.elastic.should_project(req):
            return app.data.elastic.get_projected_fields(req)

    def _get_types(self, req):
        """Get document types for the given query."""
        args = getattr(req, "args", {})
        repos = args.get("repo")
        return es_utils.get_doc_types(repos, self.repos)

    def _get_filters(self, repos, invisible_stages):
        """
        Gets filters for the passed repos.
        """
        filters = []

        for repo in repos:
            filters.append(self._get_private_filters(repo, invisible_stages))

        return [{"or": filters}] if filters else []

    def get_stages_to_exclude(self):
        """
        Returns the list of the current users invisible stages
        """
        user = g.get("user", {})
        if "invisible_stages" in user:
            stages = user.get("invisible_stages")
        else:
            stages = get_resource_service("users").get_invisible_stages_ids(user.get("_id"))

        return stages

    def get(self, req, lookup):
        """
        Runs elastic search on multiple doc types.
        """

        query = self._get_query(req)
        fields = self._get_projected_fields(req)
        types = self._get_types(req)
        excluded_stages = self.get_stages_to_exclude()
        filters = self._get_filters(types, excluded_stages)

        # if the system has a setting value for the maximum search depth then apply the filter
        if not app.settings["MAX_SEARCH_DEPTH"] == -1:
            query["terminate_after"] = app.settings["MAX_SEARCH_DEPTH"]

        if filters:
            set_filters(query, filters)

        params = {}
        if fields:
            params["_source"] = fields

        docs = self.elastic.search(query, types, params)

        for resource in types:
            response = {app.config["ITEMS"]: [doc for doc in docs if doc["_type"] == resource]}
            getattr(app, "on_fetched_resource")(resource, response)
            getattr(app, "on_fetched_resource_%s" % resource)(response)

        return docs

    def _get_docs(self, hits):
        """Parse hits from elastic and return only docs.

        This will remove some extra metadata from elastic.

        :param hits: elastic hits dictionary
        """
        return self.elastic._parse_hits(hits, "ingest")  # any resource with item schema will do

    def find_one(self, req, **lookup):
        """Find item by id in all collections."""
        _id = lookup["_id"]
        for resource in self._get_types(req):
            id_field = "item_id" if resource == "published" else "_id"
            resource_lookup = {id_field: _id}
            item = get_resource_service(resource).find_one(req=req, **resource_lookup)
            if item:
                return item

    def on_fetched(self, doc):
        """
        Overriding to add HATEOS for each individual item in the response.

        :param doc: response doc
        :type doc: dict
        """

        docs = doc[app.config["ITEMS"]]
        for item in docs:
            build_custom_hateoas({"self": {"title": item["_type"], "href": "/{}/{{_id}}".format(item["_type"])}}, item)

    def get_available_indexes(self):
        """Returns a set of the configured indexes

        :return:
        """
        return set(es_utils.get_index().split(","))


class SearchResource(superdesk.Resource):
    resource_methods = ["GET"]
    item_methods = ["GET"]
    item_url = item_url
    schema = get_schema(versioning=True)
    schema.update(published_item_fields)
    datasource = {"projection": {field: 1 for field in list(schema.keys()) + ["archive_item"]}}

    privileges = {}


def init_app(app) -> None:
    search_service = SearchService(ARCHIVE, backend=superdesk.get_backend())
    SearchResource("search", app=app, service=search_service)

    # Set the start of week config for use in both server and client
    app.client_config["start_of_week"] = app.config.get("START_OF_WEEK") or 0
