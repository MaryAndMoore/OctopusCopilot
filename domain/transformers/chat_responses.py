from datetime import datetime

import pytz

from domain.date.date_difference import get_date_difference_summary
from domain.date.parse_dates import parse_unknown_format_date
from domain.sanitizers.sanitized_list import yield_first
from infrastructure.octopus import get_channel_cached


def get_octopus_project_names_response(space_name, projects):
    """
    Provides a conversational response to the list of projects
    :param space_name: The name of the space containing the projects
    :param projects: The list of projects
    :return: A conversational response
    """

    if not projects and (space_name is None or not space_name.strip()):
        return "I found no projects."

    if not projects:
        return f"I found no projects in the space {space_name}."

    if space_name is None or not space_name.strip():
        return f"I found {len(projects)} projects:\n* " + "\n * ".join(projects)

    return f"I found {len(projects)} projects in the space \"{space_name.strip()}\":\n* " + "\n* ".join(projects)


def build_markdown_table_row(columns):
    """
    Builds a markdown table row
    :param columns: The columns
    :return: The markdown table row
    """
    if not columns:
        return ""
    return f"| {' | '.join(columns)} |\n"


def build_markdown_table_header_separator(count):
    """
    Builds a markdown table header separator
    :param count: The number of columns
    :return: The markdown table header separator
    """
    if count == 0:
        return ""

    columns = ["|"] * (count + 1)
    return "-".join(columns) + "\n"


def get_env_name(dashboard, environment_id):
    environment = next(filter(lambda e: e["Id"] == environment_id, dashboard["Environments"]), None)
    if not environment:
        return None
    return environment["Name"]


def get_dashboard_response(octopus_url, space_id, space_name, dashboard, github_actions=None,
                           github_actions_status=None, pull_requests=None, issues=None):
    now = datetime.now(pytz.utc)
    table = f"# {space_name}\n\n"

    for project_group in dashboard["ProjectGroups"]:

        environment_names = []

        # If any projects have associated GitHub workflows, add the column to the start of the table
        if github_actions_status:
            environment_names.append('GitHub')

        environment_names.extend(list(map(lambda e: get_env_name(dashboard, e), project_group["EnvironmentIds"])))

        columns = [project_group['Name'], *environment_names]
        table += build_markdown_table_row(columns)
        table += build_markdown_table_header_separator(len(columns))

        projects = list(filter(lambda p: p["ProjectGroupId"] == project_group["Id"], dashboard["Projects"]))

        for project in projects:
            table += f"| {project['Name']} "

            # Find the github repo details
            github_repo = next(
                filter(lambda x: x["ProjectId"] == project["Id"] and x["Repo"] and x["Owner"], github_actions),
                None) if github_actions else None

            # Get the GitHub Actions workflow status
            if github_actions_status:
                github_messages = []
                github_messages.extend(build_repo_link(github_repo))
                github_messages.extend(get_project_workflow_status(github_actions_status, project["Id"]))
                github_messages.extend(build_pr_response_for_project(pull_requests, project["Id"], github_repo))
                github_messages.extend(build_issue_response_for_project(issues, project["Id"], github_repo))

                if github_messages:
                    table += f"| {'<br/>'.join(github_messages)}"
                else:
                    table += f"| ⨂ "

            # Get the deployment status
            for environment in project_group["EnvironmentIds"]:
                deployment = list(
                    filter(lambda d: d["ProjectId"] == project["Id"] and d["EnvironmentId"] == environment,
                           dashboard["Items"]))

                if len(deployment) > 0:
                    last_deployment = deployment[0]

                    created = parse_unknown_format_date(last_deployment["Created"])
                    difference = get_date_difference_summary(now - created)

                    icon = get_state_icon(last_deployment['State'], last_deployment['HasWarningsOrErrors'])
                    url = build_deployment_url(octopus_url, space_id, last_deployment['ProjectId'],
                                               last_deployment['ReleaseVersion'], last_deployment['DeploymentId'])

                    messages = [
                        f"{icon} [{last_deployment['ReleaseVersion']}]({url})",
                        f"🕗 {difference} ago"]

                    table += f"| {'<br/>'.join(messages)}"
                else:
                    table += f"| ⨂ "

            table += "|\n"
        table += "\n"

    return table


def get_project_dashboard_response(octopus_url, space_id, space_name, project_name, project_id, dashboard,
                                   github_repo=None,
                                   github_actions_statuses=None,
                                   pull_requests=None,
                                   issues=None,
                                   release_workflow_runs=None,
                                   deployment_highlights=None):
    now = datetime.now(pytz.utc)

    table = f"# {space_name} / {project_name}\n\n"

    message = []
    message.extend(build_repo_link(github_repo))
    message.extend(get_project_workflow_status(github_actions_statuses, project_id))
    message.extend(build_pr_response(pull_requests, github_repo))
    message.extend(build_issue_response(issues, github_repo))

    if message:
        table += '<br/>'.join(message) + "\n\n"

    environment_names = list(map(lambda e: e["Name"], dashboard["Environments"]))
    table += build_markdown_table_row(environment_names)
    table += build_markdown_table_header_separator(len(environment_names))

    for environment in dashboard["Environments"]:
        for release in dashboard["Releases"]:
            if environment["Id"] in release["Deployments"]:
                for deployment in release["Deployments"][environment["Id"]]:
                    created = parse_unknown_format_date(deployment["Created"])
                    difference = get_date_difference_summary(now - created)
                    icon = get_state_icon(deployment['State'], deployment['HasWarningsOrErrors'])

                    release_url = build_deployment_url(octopus_url, space_id, deployment['ProjectId'],
                                                       deployment['ReleaseVersion'], deployment['DeploymentId'])

                    messages = [f"{icon} [{deployment['ReleaseVersion']}]({release_url})", f"🕗 {difference} ago"]

                    # Find the associated github workflow and build a link
                    matching_releases = yield_first(filter(
                        lambda x: x["ReleaseId"] == release["Release"]["Id"] and x.get('ShortSha') and x.get('Url'),
                        release_workflow_runs or []))

                    messages.extend(map(
                        lambda x: f"{get_github_state_icon(x.get('Status'), x.get('Conclusion'))} "
                                  + f"[{x.get('Name')} {x.get('ShortSha')}]({x.get('Url')})",
                        matching_releases))

                    # Find any highlights in the logs
                    messages.extend(map(lambda x: x['Highlights'],
                                        filter(lambda x: x["DeploymentId"] == deployment["DeploymentId"],
                                               deployment_highlights or [])))

                    table += f"| {'<br/>'.join(messages)}"
            else:
                table += "| ⨂ "
    table += "|  "
    return table


def get_tenant_environments(tenant, dashboard, project_id):
    environments_ids = []

    for project_environment in dashboard["Environments"]:
        if tenant.get("Id"):
            # Tenants have a subset of environments they are associated with.
            # We retain the environment order of the project, and then check to see if
            # the project environment is associated with the tenant
            if project_environment["Id"] in tenant.get("ProjectEnvironments", {}).get(project_id, []):
                # Add the project environment to the list
                environments_ids.append(project_environment["Id"])
        else:
            # Untenanted deployments just use project environments
            environments_ids.append(project_environment["Id"])

    return environments_ids


def get_tenant_environment_details(environments_ids, dashboard):
    environments = []
    for environment in environments_ids:
        environment_name = get_env_name(dashboard, environment)
        # Sometimes tenants will list environments that have no reference
        if environment_name:
            environments.append({"Name": environment_name, "Id": environment})

    return environments


def get_project_tenant_progression_response(space_id, space_name, project_name, project_id, dashboard,
                                            github_repo, github_actions_statuses, release_workflow_runs,
                                            pull_requests, issues, deployment_highlights, api_key, url):
    now = datetime.now(pytz.utc)

    table = f"# {space_name} / {project_name}\n\n"

    message = []
    message.extend(build_repo_link(github_repo))
    message.extend(get_project_workflow_status(github_actions_statuses, project_id))
    message.extend(build_pr_response(pull_requests, github_repo))
    message.extend(build_issue_response(issues, github_repo))

    if message:
        table += '<br/>'.join(message) + "\n\n"

    for tenant in dashboard["Tenants"]:
        table += f"## {tenant['Name']}\n"
        environments_ids = get_tenant_environments(tenant, dashboard, project_id)
        environments = get_tenant_environment_details(environments_ids, dashboard)
        environment_names = list(map(lambda e: e["Name"], environments))
        table += build_markdown_table_row(environment_names)
        table += build_markdown_table_header_separator(len(environments))

        columns = []
        for environment in environments:
            found = False
            for deployment in dashboard["Items"]:
                # Note None == None, so the untenanted deployment will satisfy this condition because
                # the tenant has no ID and neither does the deployment
                tenanted = deployment.get("TenantId") == tenant.get("Id")
                environment_match = deployment.get("EnvironmentId") == environment.get("Id")
                if environment_match and tenanted:
                    icon = get_state_icon(deployment['State'], deployment['HasWarningsOrErrors'])
                    created = parse_unknown_format_date(deployment["Created"])
                    difference = get_date_difference_summary(now - created)
                    channel = get_channel_cached(space_id, deployment["ChannelId"], api_key, url)

                    release_url = build_deployment_url(url, space_id, deployment['ProjectId'],
                                                       deployment['ReleaseVersion'], deployment['DeploymentId'])

                    messages = [f"{icon} [{deployment['ReleaseVersion']}]({release_url})", f"🔀 {channel['Name']}",
                                f"🕗 {difference} ago"]

                    # Find the associated github workflow and build a link
                    matching_releases = yield_first(filter(
                        lambda x: x["ReleaseId"] == deployment["ReleaseId"] and x.get('ShortSha') and x.get('Url'),
                        release_workflow_runs or []))

                    messages.extend(map(
                        lambda x: f"{get_github_state_icon(x.get('Status'), x.get('Conclusion'))} "
                                  + f"[{x.get('Name')} {x.get('ShortSha')}]({x.get('Url')})",
                        matching_releases))

                    # Find any highlights in the logs
                    messages.extend(map(lambda x: x['Highlights'],
                                        filter(lambda x: x["DeploymentId"] == deployment["DeploymentId"],
                                               deployment_highlights or [])))

                    columns.append("<br/>".join(messages))
                    found = True
                    break

            if not found:
                columns.append('⨂')

        if columns:
            table += build_markdown_table_row(columns)
        else:
            table += "\nNo deployments"

        table += "\n\n"
    return table


def build_runbook_run_columns(run, now, get_tenant):
    tenant_name = 'Untenanted' if not run['TenantId'] else get_tenant(run['TenantId'])
    created = parse_unknown_format_date(run["Created"])
    difference = get_date_difference_summary(now - created)
    icon = get_state_icon(run['State'], run['HasWarningsOrErrors'])
    return [tenant_name, icon + " " + difference + " ago"]


def get_tenants(dashboard):
    tenants = []
    for environment in dashboard["RunbookRuns"]:
        runs = dashboard["RunbookRuns"][environment]
        for run in runs:
            tenant = "Untenanted" if not run['TenantId'] else run['TenantId']
            if tenant not in tenants:
                tenants.append(tenant)
    return tenants


def get_runbook_dashboard_response(project, runbook, dashboard, get_tenant):
    dt = datetime.now(pytz.utc)

    table = f"{project['Name']} / {runbook['Name']}\n\n"

    tenants = get_tenants(dashboard)

    environment_ids = list(map(lambda x: x, dashboard["RunbookRuns"]))
    environment_names = list(map(lambda e: get_env_name(dashboard, e), environment_ids))
    columns = ["", *environment_names]
    table += build_markdown_table_row(columns)
    table += build_markdown_table_header_separator(len(columns))

    # Build the execution rows
    for tenant in tenants:
        for environment in environment_ids:
            runs = list(
                filter(lambda run: run['TenantId'] == tenant or (not run['TenantId'] and tenant == "Untenanted"),
                       dashboard["RunbookRuns"][environment]))
            for run in runs:
                table += build_markdown_table_row(build_runbook_run_columns(run, dt, get_tenant))

    return table


def get_state_icon(state, has_warnings):
    if state == "Executing":
        return "🔵"

    if state == "Success":
        if has_warnings:
            return "🟡"
        else:
            return "🟢"

    elif state == "Failed":
        return "🔴"

    if state == "Canceled":
        return "⚪"

    elif state == "TimedOut":
        return "🔴"

    elif state == "Cancelling":
        return "🔴"

    elif state == "Queued":
        return "🟣"

    return "⚪"


def get_github_state_icon(status, conclusion):
    # https://github.com/github/rest-api-description/issues/1634
    # Value of the status property can be one of: “queued”, “in_progress”, or “completed”.
    # When it’s “completed,” it makes sense to check if it finished successfully.
    # We need a value of the conclusion property.
    # Can be one of the “success”, “failure”, “neutral”, “cancelled”, “skipped”, “timed_out”, or “action_required”.

    if status == "in_progress":
        return "🔵"

    elif status == "queued":
        return "🟣"

    # status of completed is assumed from this point down, and we're displaying the conclusion

    if conclusion == "success":
        return "🟢"

    elif conclusion == "failure" or conclusion == "timed_out":
        return "🔴"

    elif conclusion == "action_required":
        return "🟠"

    elif conclusion == "cancelled" or conclusion == "neutral" or conclusion == "skipped":
        return "⚪"

    return "⚪"


def build_deployment_url(octopus_url, space_id, project_id, release_version, deployment_id):
    return f"{octopus_url}/app#/{space_id}/projects/{project_id}/deployments/releases/{release_version}/deployments/{deployment_id}"


def get_project_workflow_status(github_actions_statuses, project_id):
    now = datetime.now(pytz.utc)
    message = []
    if github_actions_statuses:
        github_actions_status = next(
            filter(lambda x: x["ProjectId"] == project_id and x["Status"], github_actions_statuses), None)

        if github_actions_status:
            message.append(
                f"{get_github_state_icon(github_actions_status.get('Status'), github_actions_status.get('Conclusion'))} "
                + f"[{github_actions_status.get('Name')} {github_actions_status.get('ShortSha')}]({github_actions_status.get('Url')})")

            if github_actions_status.get("CreatedAt"):
                message.append(f"🕗 {get_date_difference_summary(now - github_actions_status.get('CreatedAt'))} ago")
    return message


def build_pr_response_for_project(pull_requests, project_id, github_repo):
    if not pull_requests:
        return []

    status = next(filter(lambda x: x["ProjectId"] == project_id, pull_requests), None)
    return build_pr_response(status, github_repo)


def build_pr_response(pull_requests, github_repo):
    message = []
    if pull_requests and github_repo:
        message.append(
            f"🔁 [{pull_requests.get('Count')} PR{'s' if pull_requests.get('Count') != 1 else ''}](https://github.com/{github_repo['Owner']}/{github_repo['Repo']}/pulls)")
    return message


def build_issue_response_for_project(issues, project_id, github_repo):
    if not issues:
        return []

    status = next(filter(lambda x: x["ProjectId"] == project_id, issues), None)
    return build_issue_response(status, github_repo)


def build_issue_response(issues, github_repo):
    message = []
    if issues and github_repo:
        message.append(
            f"🐛 [{issues.get('Count')} issue{'s' if issues.get('Count') != 1 else ''}](https://github.com/{github_repo['Owner']}/{github_repo['Repo']}/issues)")
    return message


def build_repo_link(github_repo):
    message = []
    if github_repo:
        message.append(f'🗎 [GitHub Repo](https://github.com/{github_repo["Owner"]}/{github_repo["Repo"]})')
    return message
