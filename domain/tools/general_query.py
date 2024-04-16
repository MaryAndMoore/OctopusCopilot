from pydantic import BaseModel

from domain.messages.general import build_hcl_prompt
from domain.sanitizers.sanitized_list import sanitize_projects, sanitize_runbooks, sanitize_targets, sanitize_tenants, \
    sanitize_library_variable_sets, sanitize_environments, sanitize_feeds, sanitize_accounts, sanitize_certificates, \
    sanitize_lifecycles, sanitize_workerpools, sanitize_machinepolicies, sanitize_tenanttagsets, sanitize_projectgroups, \
    sanitize_channels, sanitize_releases, sanitize_steps, sanitize_gitcredentials, sanitize_space, sanitize_dates


def answer_general_query_wrapper(query, callback, logging=None):
    """
    A wrapper's job is to return a function with the signature used by the LLM to extract entities from the query. The
    parameters of the wrapper are captured by the returned function without altering the signature of the function.

    The purpose of the wrapped function is to take the entities passed in by the LLM, generate the messages passed
    to the LLM, and execute a callback with the extracted entities and the custom messages that explain how to use the
    context generated by the entities.

    The callback is then responsible for building the context, passing the messages to the LLM, and returning the
    result.

    The callback is specific to the type of system calling this agent. For example, the chat interface requires the
    agent to build the context by calling an Octopus instance. The Chrome extension will pass the context in the body
    of the request. Tests will build the context from an ephemeral instance of Octopus. Abstracting the details of how
    the context is built allows the process of extracting entities and building messages to be shared, while building
    context is implementation specific.
    """

    def answer_general_query(space=None, projects=None, runbooks=None, targets=None,
                             tenants=None, library_variable_sets=None, environments=None,
                             feeds=None, accounts=None, certificates=None, lifecycles=None,
                             worker_pools=None, machine_policies=None, tag_sets=None, project_groups=None,
                             channels=None,
                             releases=None, steps=None, variables=None, git_credentials=None, dates=None, **kwargs):
        """A query about an Octopus space.
Args:
space: Space name
projects: project names
runbooks: runbook names
targets: target/machine names
tenants: tenant names
library_variable_sets: library variable set names
environments: environment names
feeds: feed names
accounts: account names
certificates: certificate names
lifecycles: lifecycle names
workerpools: worker pool names
machinepolicies: machine policy names
tagsets: tenant tag set names
projectgroups: project group names
channels: channel names
releases: release versions
steps: step names
variables: variable names
gitcredentials: git credential names
dates: any dates in the query"""

        if logging:
            logging("Enter:", "answer_general_query")

        # This function acts as a way to extract the names of resources that are important to an Octopus query. The
        # resource names map to resources into the API that need to be queried and exposed for context to answer
        # a general question. So the only thing this function does is make another request to the LLM after
        # extracting the relevant entities from the Octopus API.

        # OpenAI will inject values for some of these lists despite the fact that there was no mention
        # of these resources anywhere in the question. We clean up the results before sending them back
        # to the client.
        body = {
            "space_name": sanitize_space(query, space),
            "project_names": sanitize_projects(projects),
            "runbook_names": sanitize_runbooks(runbooks),
            "target_names": sanitize_targets(targets),
            "tenant_names": sanitize_tenants(tenants),
            "library_variable_sets": sanitize_library_variable_sets(library_variable_sets),
            "environment_names": sanitize_environments(query, environments),
            "feed_names": sanitize_feeds(feeds),
            "account_names": sanitize_accounts(accounts),
            "certificate_names": sanitize_certificates(certificates),
            "lifecycle_names": sanitize_lifecycles(lifecycles),
            "workerpool_names": sanitize_workerpools(worker_pools),
            "machinepolicy_names": sanitize_machinepolicies(machine_policies),
            "tagset_names": sanitize_tenanttagsets(tag_sets),
            "projectgroup_names": sanitize_projectgroups(project_groups),
            "channel_names": sanitize_channels(channels),
            "release_versions": sanitize_releases(releases),
            "step_names": sanitize_steps(steps),
            "variable_names": sanitize_steps(variables),
            "gitcredential_names": sanitize_gitcredentials(git_credentials),
            "dates": sanitize_dates(dates)
        }

        for key, value in kwargs.items():
            if key not in body:
                body[key] = value
            else:
                logging(f"Conflicting Key: {key}", "Value: {value}")

        messages = build_hcl_prompt()

        return callback(query, body, messages)

    return answer_general_query


class AnswerGeneralQuery(BaseModel):
    projects: list[str] = []
    runbooks: list[str] = []
    targets: list[str] = []
    tenants: list[str] = []
    library_variable_sets: list[str] = []
    environments: list[str] = []
    feeds: list[str] = []
    accounts: list[str] = []
    certificates: list[str] = []
    lifecycles: list[str] = []
    workerpools: list[str] = []
    machinepolicies: list[str] = []
    tagsets: list[str] = []
    projectgroups: list[str] = []
