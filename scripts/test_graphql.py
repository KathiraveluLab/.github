
import os
import json
import urllib.request

TOKEN = os.environ.get("GH_TOKEN", "")
ORG = "KathiraveluLab"

def graphql_query(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

QUERY = """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $cursor) {
            pageInfo {
              hasNextPage
              endCursor
            }
            nodes {
              committedDate
            }
          }
        }
      }
    }
  }
}
"""

def test():
    # Test with .github repo
    variables = {"owner": ORG, "name": ".github", "cursor": None}
    result = graphql_query(QUERY, variables)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    test()
