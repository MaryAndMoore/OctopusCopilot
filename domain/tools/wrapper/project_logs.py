from domain.messages.deployment_logs import build_plain_text_prompt


def answer_project_deployment_logs_wrapper(query, callback, logging):
    """
    A wrapper's job is to return a function with the signature used by the LLM to extract entities from the wrapper. The
    parameters of the wrapper are captured by the returned function without altering the signature of the function.

    The purpose of the wrapped function is to take the entities passed in by the LLM, generate the messages passed
    to the LLM, and call a callback with the extracted entities and the custom messages that explain how to the context
    generated by the entities.

    The callback is then responsible for building the context, passing the messages to the LLM, and returning the result.

    The callback is specific to the type of system calling this agent. For example, the chat interface requires the agent
    to build the context by calling an Octopus instance. The Chrome extension will pass the context in the body of the
    request. Tests will build the context from an ephemeral instance of Octopus. Abstracting the details of how the
    context is built allows the process of extracting entities and building messages to be shared, while building
    context is implementation specific.
    """

    def answer_project_deployment_logs(space=None, project=None, environment=None, channel=None, tenant=None,
                                       release=None, steps=None, lines=None, **kwargs):
        """Answers a wrapper about the contents of the deployment logs of a project to an environment.
        Use this function when the prompt asks anything about deployment or project logs. Some example prompts are:
        * Print the last 30 lines of text from the deployment logs of the latest project deployment to the "Production" environment.
        * Summarize the deployment logs of the latest deployment.
        * Find any urls in the deployment logs of release version "1.0.2" to the "Development" environment for the "Contoso" tenant for the "Web App" project in the "Hotfix" channel.

        Args:
        space: Space name
        project: project names
        environment: variable names
        channel: channel name
        tenant: tenant name
        release: release version
        steps: the step names or indexes to get logs from
        lines: the number of lines from the log file to return
        """

        if logging:
            logging("Enter:", "answer_logs_usage")

        for key, value in kwargs.items():
            if logging:
                logging(f"Unexpected Key: {key}", "Value: {value}")

        messages = build_plain_text_prompt()

        # This is just a passthrough to the original callback
        return callback(query, messages, space, project, environment, channel, tenant, release, steps, lines)

    return answer_project_deployment_logs