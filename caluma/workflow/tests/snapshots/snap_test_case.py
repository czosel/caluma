# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots["test_query_all_cases 1"] = {
    "allCases": {"edges": [{"node": {"status": "RUNNING"}}]}
}

snapshots['test_start_case[["group-name"]|groups] 1'] = {
    "startCase": {
        "case": {
            "document": {"form": {"slug": "effort-meet"}},
            "parentWorkItem": {"status": "READY"},
            "status": "RUNNING",
            "workItems": {
                "edges": [
                    {"node": {"addressedGroups": ["group-name"], "status": "READY"}}
                ]
            },
        },
        "clientMutationId": None,
    }
}

snapshots["test_start_case[None] 1"] = {
    "startCase": {
        "case": {
            "document": {"form": {"slug": "effort-meet"}},
            "parentWorkItem": {"status": "READY"},
            "status": "RUNNING",
            "workItems": {
                "edges": [{"node": {"addressedGroups": [], "status": "READY"}}]
            },
        },
        "clientMutationId": None,
    }
}

snapshots["test_cancel_case[running-True-completed] 1"] = {
    "cancelCase": {
        "case": {
            "document": {"form": {"slug": "effort-meet"}},
            "status": "CANCELED",
            "workItems": {"edges": [{"node": {"status": "COMPLETED"}}]},
        },
        "clientMutationId": None,
    }
}

snapshots["test_cancel_case[running-True-ready] 1"] = {
    "cancelCase": {
        "case": {
            "document": {"form": {"slug": "effort-meet"}},
            "status": "CANCELED",
            "workItems": {"edges": [{"node": {"status": "CANCELED"}}]},
        },
        "clientMutationId": None,
    }
}
