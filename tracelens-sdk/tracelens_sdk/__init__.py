from .client import TraceLens, TraceRun, TraceStep
from .events import TraceEvent
from .decorators import traced_step
from .privacy import sanitize_payload

__version__ = "0.5.0"
__all__ = ["TraceLens", "TraceRun", "TraceStep", "TraceEvent", "traced_step", "sanitize_payload", "langchain_callback"]

def langchain_callback(*args, **kwargs):
    """Create a LangChain callback handler (requires the ``langchain`` extra)."""
    from .integrations import TraceLensCallbackHandler
    return TraceLensCallbackHandler(*args, **kwargs)

__all__.append("langchain_callback")
