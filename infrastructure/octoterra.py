import json
import os

from retry import retry
from urllib3.exceptions import HTTPError

from domain.logging.app_logging import configure_logging
from domain.query.query_inspector import exclude_all_targets, exclude_all_runbooks, exclude_all_tenants, \
    exclude_all_projects, exclude_all_library_variable_sets, exclude_all_environments, exclude_all_feeds, \
    exclude_all_accounts, exclude_all_certificates, exclude_all_lifecycles, exclude_all_worker_pools, \
    exclude_all_machine_policies, exclude_all_tagsets, exclude_all_project_groups
from domain.strings.sanitized_list import sanitize_projects, sanitize_tenants, sanitize_targets, \
    sanitize_runbooks, sanitize_library_variable_sets, sanitize_environments, sanitize_feeds, sanitize_accounts, \
    sanitize_certificates, sanitize_lifecycles, sanitize_workerpools, sanitize_machinepolicies, sanitize_tenanttagsets, \
    sanitize_projectgroups
from domain.validation.argument_validation import ensure_string_not_empty
from infrastructure.http_pool import http
from infrastructure.octopus import handle_response, get_space_id_and_name_from_name

logger = configure_logging(__name__)


@retry(HTTPError, tries=3, delay=2)
def get_octoterra_space(query, space_name, project_names, runbook_names, target_names, tenant_names,
                        library_variable_sets, environment_names, feed_names, account_names, certificate_names,
                        lifecycle_names, workerpool_names, machinepolicy_names, tagset_names, projectgroup_names,
                        api_key, octopus_url):
    """
    Returns the terraform representation of a space
    :param space_name: The name of the space.
    :param project_names: The names of the projects to limit the export to.
    :param api_key: The Octopus API key
    :param octopus_url: The Octopus URL
    :return: The space terraform module
    """
    logger.info("get_octoterra_space - Enter")

    ensure_string_not_empty(space_name, 'space_name must be a non-empty string (get_octoterra_space).')
    ensure_string_not_empty(query, 'query must be a non-empty string (get_octoterra_space).')
    ensure_string_not_empty(api_key, 'api_key must be a non-empty string (get_octoterra_space).')
    ensure_string_not_empty(octopus_url, 'octopus_url must be a non-empty string (get_octoterra_space).')

    space_id, actual_space_name = get_space_id_and_name_from_name(space_name, api_key, octopus_url)

    # We want to restrict the size of the exported Terraform configuration as much as possible,
    # so we make heavy use of the options to exclude resources unless they were mentioned in the query.
    sanitized_project_names = sanitize_projects(project_names)
    sanitized_tenant_names = sanitize_tenants(tenant_names)
    sanitized_target_names = sanitize_targets(target_names)
    sanitized_runbook_names = sanitize_runbooks(runbook_names)
    sanitized_library_variable_sets = sanitize_library_variable_sets(library_variable_sets)
    sanitized_environments = sanitize_environments(environment_names)
    sanitized_feeds = sanitize_feeds(feed_names)
    sanitized_accounts = sanitize_accounts(account_names)
    sanitized_certificates = sanitize_certificates(certificate_names)
    sanitized_lifecycles = sanitize_lifecycles(lifecycle_names)
    sanitized_workerpools = sanitize_workerpools(workerpool_names)
    sanitized_machinepolicies = sanitize_machinepolicies(machinepolicy_names)
    sanitized_tagsets = sanitize_tenanttagsets(tagset_names)
    sanitized_projectgroups = sanitize_projectgroups(projectgroup_names)

    body = {
        "space": space_id,
        "url": octopus_url,
        "apiKey": api_key,
        "ignoreCacManagedValues": False,
        "excludeCaCProjectSettings": True,
        "excludeProjectsExcept": sanitized_project_names if sanitized_project_names else None,
        "excludeTenantsExcept": sanitized_tenant_names if sanitized_tenant_names else None,
        "excludeEnvironmentsExcept": sanitized_environments if sanitized_environments else None,
        "excludeFeedsExcept": sanitized_feeds if sanitized_feeds else None,
        "excludeAccountsExcept": sanitized_accounts if sanitized_accounts else None,
        "excludeCertificatesExcept": sanitized_certificates if sanitized_certificates else None,
        "excludeLifecyclesExcept": sanitized_lifecycles if sanitized_lifecycles else None,
        "excludeWorkerPoolsExcept": sanitized_workerpools if sanitized_workerpools else None,
        "excludeMachinePoliciesExcept": sanitized_machinepolicies if sanitized_machinepolicies else None,
        "excludeTagSetsExcept": sanitized_tagsets if sanitized_tagsets else None,
        "excludeProjectGroupsExcept": sanitized_projectgroups if sanitized_projectgroups else None,
        "excludeAllProjects": exclude_all_projects(query, sanitized_project_names),
        "excludeAllTenants": exclude_all_tenants(query, sanitized_tenant_names),
        "excludeAllTargets": exclude_all_targets(query, sanitized_target_names),
        "excludeAllRunbooks": exclude_all_runbooks(query, sanitized_runbook_names),
        "excludeAllFeeds": exclude_all_feeds(query, sanitized_feeds),
        "excludeAllAccounts": exclude_all_accounts(query, sanitized_accounts),
        "excludeAllEnvironments": exclude_all_environments(query, sanitized_environments),
        "excludeAllCertificates": exclude_all_certificates(query, sanitized_certificates),
        "excludeAllLifecycles": exclude_all_lifecycles(query, sanitized_lifecycles),
        "excludeAllWorkerPools": exclude_all_worker_pools(query, sanitized_workerpools),
        "excludeAllMachinePolicies": exclude_all_machine_policies(query, sanitized_machinepolicies),
        "excludeAllTagSets": exclude_all_tagsets(query, sanitized_tagsets),
        "excludeAllProjectGroups": exclude_all_project_groups(query, sanitized_projectgroups),
        "excludeAllLibraryVariableSets": exclude_all_library_variable_sets(query, sanitized_library_variable_sets),
        "limitAttributeLength": 100,
        # This setting ensures that any project, tenant, runbook, or target names are valid.
        # If not, the assumption is made that the LLM incorrectly identified the resource in the query,
        # and the results must not be limited by that incorrect assumption.
        "ignoreInvalidExcludeExcept": True,
        "excludeTerraformVariables": True,
        "excludeSpaceCreation": True,
        "excludeProvider": True,
    }

    resp = handle_response(lambda: http.request("POST",
                                                os.environ["APPLICATION_OCTOTERRA_URL"] + "/api/octoterra",
                                                body=json.dumps(body)))

    return resp.data.decode("utf-8")
