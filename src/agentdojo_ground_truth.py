"""Ground truth execution for injection candidate discovery.

Replaces GroundTruthPipeline with a standalone function that executes
a task's ground_truth() tool calls directly against the FunctionsRuntime.
"""


import yaml
from pydantic import BaseModel

from agentdojo.base_tasks import BaseInjectionTask, BaseUserTask
from agentdojo.functions_runtime import FunctionReturnType, FunctionsRuntime, TaskEnvironment
from agentdojo_results import ToolCallRecord


def tool_result_to_str(tool_result: FunctionReturnType) -> str:
    """Format a tool result as a YAML string."""
    if isinstance(tool_result, BaseModel):
        return yaml.safe_dump(tool_result.model_dump()).strip()

    if isinstance(tool_result, list):
        res_items = []
        for item in tool_result:
            if type(item) in [str, int]:
                res_items += [str(item)]
            elif isinstance(item, BaseModel):
                res_items += [item.model_dump()]
            else:
                raise TypeError("Not valid type for item tool result: " + str(type(item)))
        return yaml.safe_dump(res_items).strip()

    return str(tool_result)


def execute_ground_truth(
    task: BaseUserTask | BaseInjectionTask,
    runtime: FunctionsRuntime,
    env: TaskEnvironment,
) -> tuple[list[ToolCallRecord], list[str]]:
    """Execute a task's ground_truth() tool calls directly.

    Returns:
        A tuple of (tool_call_records, tool_output_strings).
        tool_output_strings are the formatted results of each tool call,
        used for injection candidate discovery (canary detection).
    """
    ground_truth_calls = task.ground_truth(env)
    records = []
    outputs = []

    for tc in ground_truth_calls:
        result, error = runtime.run_function(env, tc.function, tc.args, raise_on_error=True)
        formatted = tool_result_to_str(result)
        records.append(ToolCallRecord(
            function=tc.function,
            args=dict(tc.args),
            result=formatted,
            error=error,
        ))
        outputs.append(formatted)

    return records, outputs


def get_injection_candidates(
    task: BaseUserTask,
    runtime: FunctionsRuntime,
    env: TaskEnvironment,
    canary_injections: dict[str, str],
) -> list[str]:
    """Discover which injection vectors are visible during correct task execution.

    Runs the task's ground truth with canary strings substituted at each
    injection vector. Returns the list of vector IDs whose canaries appear
    in tool outputs.
    """
    _, outputs = execute_ground_truth(task, runtime, env)
    all_output = " ".join(outputs)

    candidates = []
    for vector_id, canary in canary_injections.items():
        if canary in all_output:
            candidates.append(vector_id)

    return candidates
