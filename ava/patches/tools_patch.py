"""Monkey patch to inject CafeExt custom tools into AgentLoop."""

from nanobot.agent.loop import AgentLoop
from ava.launcher import register_patch

from ava.tools import (
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

        # ClaudeCodeConfig is at tools.claude_code (fork schema)
        # Fallback gracefully if the field doesn't exist (vanilla schema)
        cc_cfg = getattr(getattr(config, "tools", None), "claude_code", None)
        cc_model = (cc_cfg.model if cc_cfg else None) or \
                   getattr(getattr(config.agents.defaults, None, None), "claude_code_model", None) or \
                   "claude-sonnet-4-20250514"
        cc_max_turns = cc_cfg.max_turns if cc_cfg else 15
        cc_allowed_tools = cc_cfg.allowed_tools if cc_cfg else "Read,Edit,Bash,Glob,Grep"
        cc_timeout = cc_cfg.timeout if cc_cfg else 600

        self.tools.register(ClaudeCodeTool(
            workspace=self.workspace,
            token_stats=getattr(self, 'token_stats', None),
            default_project=str(self.workspace),
            model=cc_model,
            max_turns=cc_max_turns,
            allowed_tools=cc_allowed_tools,
            timeout=cc_timeout,
            subagent_manager=self.subagents,
            cc_config=cc_cfg,
        ))
        
        self.tools.register(ImageGenTool(
            token_stats=getattr(self, 'token_stats', None),
            media_service=getattr(self, 'media_service', None),
        ))

        # Vision tool: prefer vision_model if configured
        vision_model = getattr(config.agents.defaults, "vision_model", None) or self.model
        self.tools.register(VisionTool(
            provider=self.provider,
            model=vision_model,
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
