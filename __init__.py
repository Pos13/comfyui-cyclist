"""
@author: Pos13
@title: Cyclist
@nickname: comfyui-cyclist
@description: This extension provides tools to iterate generation results between runs. In general, it's for cycles.
"""

#import inspect
from .cyclist import *
from .util_nodes import *

WEB_DIRECTORY = "./js"
NODE_CLASS_MAPPINGS = {
    "Interrupt": CyclistInterrupt, 

    "ReloadImage": ReloadImage, 
    "OverrideImage": OverrideImage,
    "ReloadLatent": ReloadLatent, 
    "OverrideLatent": OverrideLatent,
    "ReloadModel": ReloadModel, 
    "OverrideModel": OverrideModel,

    "RecallString": RecallString, 
    "MemorizeString": MemorizeString, 
    "RecallInt": RecallInt, 
    "MemorizeInt": MemorizeInt, 
    "RecallFloat": RecallFloat, 
    "MemorizeFloat": MemorizeFloat, 
    "RecallConditioning": RecallConditioning, 
    "MemorizeConditioning": MemorizeConditioning, 
      
    "CyclistMathInt": CyclistMathInt, 
    "CyclistMathFloat": CyclistMathFloat, 
    "CyclistTypeCast": CyclistTypeCast, 
    "CyclistCompare": CyclistCompare, 
    "CyclistTimer": CyclistTimer, 
    "CyclistTimerStop": CyclistTimerStop
}
NODE_DISPLAY_NAME_MAPPINGS = {
    "Interrupt": "Interrupt", 
    "RecallString": "Recall String", 
    "MemorizeString": "Memorize String", 
    "RecallInt": "Recall Int", 
    "MemorizeInt": "Memorize Int", 
    "RecallFloat": "Recall Float", 
    "MemorizeFloat": "Memorize Float", 
    "RecallConditioning": "Recall Conditioning", 
    "MemorizeConditioning": "Memorize Conditioning", 
    "ReloadLatent": "Reload Latent", 
    "OverrideLatent": "Save Latent (Override)", 
    "ReloadImage": "Reload Image", 
    "OverrideImage": "Save Image (Override)", 
    "ReloadModel": "Reload Model", 
    "OverrideModel": "Save Model (Override)", 
    "CyclistTimer": "Generation Timer", 
    "CyclistTimerStop": "Force Timer Stop", 
    "CyclistMathFloat": "Float Math", 
    "CyclistMathInt": "Int Math", 
    "CyclistTypeCast": "Convert to", 
    "CyclistCompare": "Compare Anything"
}
# Sadly, this automatic mapping is abandoned for Manager compatibility
"""NODE_CLASS_MAPPINGS = {}

for name, obj in (list(reversed(inspect.getmembers(cyclist))) + inspect.getmembers(util_nodes)):
    if inspect.isclass(obj):
        if hasattr(obj, 'NODE_NAME'):
            node_name = getattr(obj, 'NODE_NAME', name)
            NODE_CLASS_MAPPINGS[node_name] = obj"""

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
