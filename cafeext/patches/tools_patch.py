"""Monkey patch to inject CafeExt custom tools into AgentLoop."""

from nanobot.agent.loop import AgentLoop
from cafeext.launcher import register_patch

from cafeext.tools import (
    ClaudeCodeTool,
    ImageGenTool,
    MemoryTool,
    StickerTool,
    VisionTool,
)


def apply_tools_patch() -> str:
    """Apply the custom tools patch to AgentLoop.
    
    This function:
    1. Saves the original _register_default_tools method
    2. Creates a wrapper that calls the original method first
    3. Then registers the 5 CafeExt custom tools
    4. Replaces the method on AgentLoop class
    
    Returns:
        str: Description of what was patched
    """
    original_register = AgentLoop._register_default_tools

    def patched_register_default_tools(self: AgentLoop) -> None:
        """Wrapper that registers default tools then adds CafeExt custom tools."""
        original_register(self)
        
        from nanobot.config.loader import load_config
        config = load_config()
        
        cc_config = config.agents.defaults.claude_code_config or None
        
        self.tools.register(ClaudeCodeTool(
            workspace=self.workspace,
            token_stats=getattr(self, 'token_stats', None),
            default_project=str(self.workspace),
            model=config.agents.defaults.claude_code_model or "claude-sonnet-4-20250514",
            max_turns=15,
            allowed_tools="Read,Edit,Bash,Glob,Grep",
            timeout=600,
            subagent_manager=self.subagents,
            cc_config=cc_config,
        ))
        
        self.tools.register(ImageGenTool(
            token_stats=getattr(self, 'token_stats', None),
            media_service=getattr(self, 'media_service', None),
        ))
        
        self.tools.register(VisionTool(
            provider=self.provider,
            model=self.model,
            token_stats=getattr(self, 'token_stats', None),
        ))
        
        self.tools.register(StickerTool())
        
        categorized_memory = getattr(self, 'categorized_memory', None)
        db = getattr(self, 'db', None)
        if categorized_memory:
            self.tools.register(MemoryTool(
                store=categorized_memory,
                db=db,
            ))

    AgentLoop._register_default_tools = patched_register_default_tools
    
    return "Registered 5 custom tools: claude_code, image_gen, vision, send_sticker, memory"


register_patch('custom_tools', apply_tools_patch)
