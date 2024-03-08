import json
import os
import hashlib
import logging
import time
import sys

import numpy as np
import torch
import safetensors.torch
from PIL import Image, ImageOps
from PIL.PngImagePlugin import PngInfo

import folder_paths
from folder_paths import folder_names_and_paths
import nodes
import comfy.utils
import comfy.sd
import comfy.model_base
from comfy.cli_args import args
from server import PromptServer

DEFAULT_LOOP_ID = "ForLoop_1"

cyclist_memory = {}

# 'required' input can't be '*', unless it can. Thanks, @pythongossss
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

class CyclistInterrupt:
    """A node to stop generation immediately if conditions are met"""

    @classmethod
    def INPUT_TYPES(s):
        return { "required": {"any_in": (AnyType("*"), )},
                 "optional": {"stop": ("BOOLEAN", {"default": False, "label_on": "interrupt", "label_off": "continue"})}}
    
    RETURN_TYPES = (AnyType("*"), )
    FUNCTION = "stop"
    CATEGORY = "cyclist"

    #NODE_NAME = "Interrupt"

    def stop(self, any_in, stop=False):
        if stop:
            self.interrupt()
        else:
            PromptServer.instance.send_sync("cyclist.message.popup", {"stop": False, "message" : ""})
        return (any_in,)
    
    @classmethod
    def IS_CHANGED(self, any_id, stop=False):
        if stop:
            self.interrupt()
        return False # Always the same value, as it's never changed unless inputs were
    
    def interrupt(self):
        nodes.interrupt_processing(True)
        message = "Processing is intentionally interrupted by 'Interrupt' node.\nGuess the work is done! 😎"
        print(message)
        PromptServer.instance.send_sync("cyclist.message.popup", {"stop": True, "message" : message})
        #logging.info(message)
        #raise Exception(message)

class CyclistRead:
    """Base class for loading. All nodes from "Read" inherit it."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "loop_id": ("STRING", {"default": DEFAULT_LOOP_ID})}, 
                "optional": { "fallback": ("*", )}}

    CATEGORY = "cyclist/Read"
    FUNCTION = "read"

    VAR_TYPE = AnyType("*")

    @classmethod
    def update(self):
        pass
    
    def read(self, loop_id, fallback=None):
        global cyclist_memory
        if loop_id in cyclist_memory:
            if self.VAR_TYPE in cyclist_memory[loop_id]:
                if "value" in cyclist_memory[loop_id][self.VAR_TYPE]:
                    return (cyclist_memory[loop_id][self.VAR_TYPE]["value"], )
        if fallback is None:
            err = f"ERROR: No {self.VAR_TYPE} for loop with id={loop_id}, and fallback is not provided."
            print(err)
            raise Exception(err)
        
        self.update()
        return (fallback, )
    
    @classmethod
    def IS_CHANGED(self, loop_id, fallback=None):
        global cyclist_memory
        if loop_id in cyclist_memory:
            if self.VAR_TYPE in cyclist_memory[loop_id]:
                if "value" in cyclist_memory[loop_id][self.VAR_TYPE]:
                    return (cyclist_memory[loop_id][self.VAR_TYPE]["value"], )
        if not fallback is None:
            return fallback
        return float("NaN")

class CyclistWrite:
    """Base class for saving. All nodes from "Write" inherit it."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "loop_id": ("STRING", {"default": DEFAULT_LOOP_ID}), 
                              "to_memory": ("STRING", {"forceInput": True})}}
    
    RETURN_TYPES = ()
    FUNCTION = "write"
    OUTPUT_NODE = True
    CATEGORY = "cyclist/Write"

    VAR_TYPE = AnyType("*")

    @classmethod
    def update(self, loop_id="undefined_loop"):
        global cyclist_memory
        if not loop_id in cyclist_memory:
            cyclist_memory[loop_id] = {}
        if not self.VAR_TYPE in cyclist_memory[loop_id]:
            cyclist_memory[loop_id][self.VAR_TYPE] = {"counter": 0}
        
        cyclist_memory[loop_id][self.VAR_TYPE]["counter"] += 1
        #PromptServer.instance.send_sync("cyclist.message.counter", {"message" : counter})
        LoopTimer.getLoopTimer(loop_id).report_output_time()
        return cyclist_memory[loop_id][self.VAR_TYPE]["counter"]
    
    def write(self, loop_id, to_memory):
        global cyclist_memory
        if not loop_id in cyclist_memory:
            cyclist_memory[loop_id] = {}
        if not self.VAR_TYPE in cyclist_memory[loop_id]:
            cyclist_memory[loop_id][self.VAR_TYPE] = {"counter": 0}
        
        cyclist_memory[loop_id][self.VAR_TYPE]["value"] = to_memory
        counter = self.update(loop_id)
        return {"ui": {"loop_id": (loop_id, ), "counter": (counter, )}} # and "results": (to_memory, ) ?
      
#---------- PRIMITIVES ----------

class RecallString(CyclistRead):
    """Node to read a string from a global memory"""

    #NODE_NAME = "Recall String"
    RETURN_TYPES = ("STRING", )
    VAR_TYPE = "STRING"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["optional"]["fallback"] = ("STRING", {"default": ""})
       return result

class MemorizeString(CyclistWrite):
    """Node to put a string into a global memory"""

    #NODE_NAME = "Memorize String"
    VAR_TYPE = "STRING"

class RecallInt(CyclistRead):
    """Node to read an integer number from a global memory"""

    #NODE_NAME = "Recall Int"
    RETURN_TYPES = ("INT", )
    VAR_TYPE = "INT"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["optional"]["fallback"] = ("INT", {"default": 0, "min": -sys.maxsize, "max": sys.maxsize})
       return result

class MemorizeInt(CyclistWrite):
    """Node to put an integer number into a global memory"""

    #NODE_NAME = "Memorize Int"
    VAR_TYPE = "INT"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["required"]["to_memory"] = ("INT", {"forceInput": True})
       return result

class RecallFloat(CyclistRead):
    """Node to read a float number from a global memory"""

    #NODE_NAME = "Recall Float"
    RETURN_TYPES = ("FLOAT", )
    VAR_TYPE = "FLOAT"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["optional"]["fallback"] = ("FLOAT", {"default": 1.0, "min": -sys.float_info.max, "max": sys.float_info.max})
       return result

class MemorizeFloat(CyclistWrite):
    """Node to put a float number into a global memory"""

    #NODE_NAME = "Memorize Float"
    VAR_TYPE = "FLOAT"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["required"]["to_memory"] = ("FLOAT", {"forceInput": True})
       return result

#---------- CONDITIONING ----------

class RecallConditioning(CyclistRead):
    """Node to read a conditioning from a global memory"""

    #NODE_NAME = "Recall Conditioning"
    RETURN_TYPES = ("CONDITIONING", )
    VAR_TYPE = "CONDITIONING"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["optional"]["fallback"] = ("CONDITIONING", )
       return result
    
    @classmethod
    def IS_CHANGED(self, loop_id, fallback=None):
        return float("NaN") # Conditionings are BIG. It's probably easier to get a new one than compare existing ones

class MemorizeConditioning(CyclistWrite):
    """Node to put a conditioning into a global memory"""

    #NODE_NAME = "Memorize Conditioning"
    VAR_TYPE = "CONDITIONING"

    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["required"]["to_memory"] = ("CONDITIONING", )
       return result

#---------- LATENT ----------

class ReloadLatent(CyclistRead):
    """Node to load latent from a file. If not present, returns fallback instead.""" # Mostly copy-pasted LoadLatent
    
    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["required"]["filename"] = result["required"].pop("loop_id")
       result["optional"]["fallback"] = ("LATENT",)
       return result
    
    RETURN_TYPES = ("LATENT", )
    #NODE_NAME = "Reload Latent"

    @classmethod
    def GET_DIR(self):
        return os.path.join(folder_paths.get_output_directory(), 'latents')

    def read(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadLatent.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.latent"
        full_filepath = os.path.join(folder, filename)

        try:
            latent = safetensors.torch.load_file(full_filepath, device="cpu")
            multiplier = 1.0
            if "latent_format_version_0" not in latent:
                multiplier = 1.0 / 0.18215
            samples = {"samples": latent["latent_tensor"].float() * multiplier}
        except:
            if fallback is None:
                err = f"ERROR: Can't load latent file, and fallback is not provided. \nLoad path: {full_filepath}"
                print(err)
                raise Exception(err)
            samples = fallback
        
        self.update()
        return (samples, )

    @classmethod
    def IS_CHANGED(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadLatent.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.latent"
        full_filepath = os.path.join(folder, filename)
        try:
            m = hashlib.sha256()
            with open(full_filepath, 'rb') as f:
                m.update(f.read())
            return m.digest().hex()
        except:
            return float("NaN")

class OverrideLatent(CyclistWrite):
    """Node to save latent to a file, overriding if need to.""" # Mostly copy-pasted SaveLatent

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "filename": ("STRING", {"default": DEFAULT_LOOP_ID}), 
                              "samples": ("LATENT", ),},
                "hidden": { "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }
    
    #NODE_NAME = "Save Latent (Override)"
    VAR_TYPE = "LATENT"

    @classmethod
    def GET_DIR(self):
        return os.path.join(folder_paths.get_output_directory(), 'latents')
    
    def write(self, filename, samples, prompt=None, extra_pnginfo=None):
        loop_id = filename

        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(OverrideLatent.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.latent"
        full_filepath = os.path.join(folder, filename)

        prompt_info = ""
        if prompt is not None:
            prompt_info = json.dumps(prompt)

        metadata = None
        if not args.disable_metadata:
            metadata = {"prompt": prompt_info}
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])

        results = list()
        results.append({
            "filename": filename,
            "subfolder": subfolder,
            "type": "output"
        })

        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)

        output = {}
        output["latent_tensor"] = samples["samples"]
        output["latent_format_version_0"] = torch.tensor([])
        comfy.utils.save_torch_file(output, full_filepath, metadata=metadata)

        counter = self.update(loop_id)
        return { "ui": { "latents": results, "loop_id": (loop_id, ), "counter": (counter, )} }

#---------- IMAGE ----------

class ReloadImage(CyclistRead):
    """Node to load image from a file. If not present, returns fallback instead.""" # Mostly copy-pasted LoadImage
    
    @classmethod
    def INPUT_TYPES(s):
       result = super().INPUT_TYPES()
       result["required"]["filename"] = result["required"].pop("loop_id")
       result["optional"]["fallback"] = ("IMAGE",)
       return result
    
    RETURN_TYPES = ("IMAGE", )
    #NODE_NAME = "Reload Image"

    @classmethod
    def GET_DIR(self):
        return folder_paths.get_output_directory()

    def read(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadImage.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.png"
        full_filepath = os.path.join(folder, filename)

        try:
            image = Image.open(full_filepath)
            if getattr(image, "is_animated", False):
                image = image.seek(0) # No animation support so far.
            i = ImageOps.exif_transpose(image)
            if i.mode == 'I':
                i = i.point(lambda i: i * (1 / 255))
            image = i.convert("RGB")
            image = np.array(image).astype(np.float32) / 255.0
            image = torch.from_numpy(image)[None,]
        except:
            if fallback is None:
                err = f"ERROR: Can't load image file, and fallback is not provided. \nLoad path: {full_filepath}"
                print(err)
                raise Exception(err)
            image = torch.unsqueeze(fallback[0], 0) # Remake batch with only 1st image
        
        self.update()
        return (image, )

    @classmethod
    def IS_CHANGED(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadImage.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.png"
        full_filepath = os.path.join(folder, filename)
        try:
            m = hashlib.sha256()
            with open(full_filepath, 'rb') as f:
                m.update(f.read())
            return m.digest().hex()
        except:
            return float("NaN")
      
class OverrideImage(CyclistWrite):
    """Node to save image to a file, overriding if need to.""" # Mostly copy-pasted SaveImage

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "filename": ("STRING", {"default": DEFAULT_LOOP_ID}), 
                              "image": ("IMAGE", ),},
                "hidden": { "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }
    
    #NODE_NAME = "Save Image (Override)"
    VAR_TYPE = "IMAGE"

    @classmethod
    def GET_DIR(self):
        return folder_paths.get_output_directory()
    
    def write(self, filename, image, prompt=None, extra_pnginfo=None):
        loop_id = filename

        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(OverrideImage.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.png"
        full_filepath = os.path.join(folder, filename)

        image = image[0] # Take 1st from batch. Other CyclistWrite nodes have no batch support - why this should?
        i = 255. * image.cpu().numpy()
        img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

        metadata = None
        if not args.disable_metadata:
            metadata = PngInfo()
            if prompt is not None:
                metadata.add_text("prompt", json.dumps(prompt))
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata.add_text(x, json.dumps(extra_pnginfo[x]))

        results = list()
        results.append({
            "filename": filename,
            "subfolder": subfolder,
            "type": "output"
        })

        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        img.save(full_filepath, pnginfo=metadata, compress_level=4)
        
        counter = self.update(loop_id)
        return { "ui": { "images": results, "loop_id": (loop_id, ), "counter": (counter, )} }

#---------- Model ----------

class ReloadModel(CyclistRead):
    """Node to load model from a file. If not present, returns fallback instead.""" # CheckpointLoaderSimple analog
    
    @classmethod
    def INPUT_TYPES(s):
       return { "required": { "filename": ("STRING", {"default": DEFAULT_LOOP_ID})}, 
                "optional": { "fallback_m": ("MODEL", ),
                              "fallback_c": ("CLIP", ),
                              "fallback_v": ("VAE", )}, }
    
    RETURN_TYPES = ("MODEL", "CLIP", "VAE", )
    #NODE_NAME = "Reload Model"

    @classmethod
    def GET_DIR(self):
        try:
            result = folder_names_and_paths["checkpoints"][0][0]
            return result
        except:
            result = folder_paths.get_output_directory()
            return result

    def read(self, filename, fallback_m=None, fallback_c=None, fallback_v=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadModel.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.safetensors"
        full_filepath = os.path.join(folder, filename)

        try:
            result = comfy.sd.load_checkpoint_guess_config(full_filepath, output_vae=True, output_clip=True, embedding_directory=folder_paths.get_folder_paths("embeddings"))
        except:
            msg = f"WARNING: Can't load model file. "
            if fallback_m is None:
                msg += "Model fallback is not provided. "
            if fallback_c is None:
                msg += "CLIP fallback is not provided. "
            if fallback_v is None:
                msg += "VAE fallback is not provided. "
            msg += f"\nLoad path: {full_filepath}"
            logging.warn(msg) # Not an exception, because user might only need some of the ouputs, not all of them
            result = (fallback_m, fallback_c, fallback_v)
        
        self.update()
        return result[:3]

    @classmethod
    def IS_CHANGED(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadModel.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.safetensors"
        full_filepath = os.path.join(folder, filename)
        try:
            m = hashlib.sha256()
            with open(full_filepath, 'rb') as f:
                m.update(f.read())
            return m.digest().hex()
        except:
            return float("NaN")

class OverrideModel(CyclistWrite):
    """Node to save model to a file, overriding if need to.""" # Mostly copy-pasted save_checkpoint()

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "filename": ("STRING", {"default": DEFAULT_LOOP_ID}), 
                              "model": ("MODEL",),
                              "clip": ("CLIP",),
                              "vae": ("VAE",)},
                "hidden": { "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }
    
    #NODE_NAME = "Save Model (Override)"
    VAR_TYPE = "MODEL"

    @classmethod
    def GET_DIR(self):
        try:
            result = folder_names_and_paths["checkpoints"][0][0]
            return result
        except:
            result = folder_paths.get_output_directory()
            return result
    
    def write(self, filename, model, clip, vae, prompt=None, extra_pnginfo=None):
        loop_id = filename

        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(OverrideModel.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.safetensors"
        full_filepath = os.path.join(folder, filename)

        prompt_info = ""
        if prompt is not None:
            prompt_info = json.dumps(prompt)

        metadata = {}

        enable_modelspec = True
        if isinstance(model.model, comfy.model_base.SDXL):
            metadata["modelspec.architecture"] = "stable-diffusion-xl-v1-base"
        elif isinstance(model.model, comfy.model_base.SDXLRefiner):
            metadata["modelspec.architecture"] = "stable-diffusion-xl-v1-refiner"
        else:
            enable_modelspec = False

        if enable_modelspec:
            metadata["modelspec.sai_model_spec"] = "1.0.0"
            metadata["modelspec.implementation"] = "sgm"
            metadata["modelspec.title"] = filename

        if model.model.model_type == comfy.model_base.ModelType.EPS:
            metadata["modelspec.predict_key"] = "epsilon"
        elif model.model.model_type == comfy.model_base.ModelType.V_PREDICTION:
            metadata["modelspec.predict_key"] = "v"

        if not args.disable_metadata:
            metadata["prompt"] = prompt_info
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])

        comfy.sd.save_checkpoint(full_filepath, model, clip, vae, clip_vision=None, metadata=metadata)

        counter = self.update(loop_id)
        return {"ui": {"loop_id": (loop_id, ), "counter": (counter, )}}

# Not implemented yet, because CLIP object can actually consist of several CLIPs, and it (probably) requires to save/load using several files
"""
#---------- CLIP ----------

class ReloadCLIP(CyclistRead):
    #Node to load CLIP from a file. If not present, returns fallback instead. # Mostly copy-pasted CLIPLoader
    
    @classmethod
    def INPUT_TYPES(s):
       return {"required": { "filename": ("STRING", {"default": DEFAULT_LOOP_ID}),
                             "type": (["stable_diffusion", "stable_cascade"])}, 
                "optional": { "fallback": ("CLIP", )}}
    
    RETURN_TYPES = ("CLIP", )
    NODE_NAME = "Reload CLIP"

    @classmethod
    def GET_DIR(self):
        try:
            result = folder_names_and_paths["clip"][0][0]
            return result
        except:
            result = folder_paths.get_output_directory()
            return result

    def read(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadCLIP.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.safetensors"
        full_filepath = os.path.join(folder, filename)

        try:
            clip_type = comfy.sd.CLIPType.STABLE_DIFFUSION
            if type == "stable_cascade":
                clip_type = comfy.sd.CLIPType.STABLE_CASCADE

            #clip_path = folder_paths.get_full_path("clip", filename)
            clip = comfy.sd.load_clip([full_filepath], folder_paths.get_folder_paths("embeddings"), clip_type)
        except:
            if fallback is None:
                err = f"ERROR: Can't load CLIP file, and fallback is not provided. \nLoad path: {full_filepath}"
                print(err)
                raise Exception(err)
            clip = fallback
        
        self.update()
        return (clip, )

    @classmethod
    def IS_CHANGED(self, filename, fallback=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(ReloadCLIP.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.safetensors"
        full_filepath = os.path.join(folder, filename)
        try:
            m = hashlib.sha256()
            with open(full_filepath, 'rb') as f:
                m.update(f.read())
            return m.digest().hex()
        except:
            return float("NaN")

class OverrideCLIP(CyclistWrite):
    #Node to save CLIP to a file, overriding if need to. # Mostly copy-pasted CLIPSave

    @classmethod
    def INPUT_TYPES(s):
        return {"required": { "filename": ("STRING", {"default": DEFAULT_LOOP_ID}), 
                              "CLIP": ("CLIP", ),},
                "hidden": { "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"},
                }
    
    NODE_NAME = "Save CLIP (Override)"

    @classmethod
    def GET_DIR(self):
        try:
            result = folder_names_and_paths["clip"][0][0]
            return result
        except:
            result = folder_paths.get_output_directory()
            return result
    
    def write(self, filename, clip, prompt=None, extra_pnginfo=None):
        subfolder = os.path.dirname(os.path.normpath(filename))
        folder = os.path.join(OverrideCLIP.GET_DIR(), subfolder)
        filename = os.path.basename(os.path.normpath(filename))
        filename = f"{filename}.safetensors"
        full_filepath = os.path.join(folder, filename)

        prompt_info = ""
        if prompt is not None:
            prompt_info = json.dumps(prompt)

        metadata = {}
        if not args.disable_metadata:
            metadata["prompt"] = prompt_info
            if extra_pnginfo is not None:
                for x in extra_pnginfo:
                    metadata[x] = json.dumps(extra_pnginfo[x])

        comfy.model_management.load_models_gpu([clip.load_model()])
        clip_sd = clip.get_sd()

        for prefix in ["clip_l.", "clip_g.", ""]:
            k = list(filter(lambda a: a.startswith(prefix), clip_sd.keys()))
            current_clip_sd = {}
            for x in k:
                current_clip_sd[x] = clip_sd.pop(x)
            if len(current_clip_sd) == 0:
                continue

            p = prefix[:-1]
            replace_prefix = {}
            if len(p) > 0:
                replace_prefix[prefix] = ""
            replace_prefix["transformer."] = ""

            current_clip_sd = comfy.utils.state_dict_prefix_replace(current_clip_sd, replace_prefix)

            comfy.utils.save_torch_file(current_clip_sd, full_filepath, metadata=metadata)

        self.update()
        return {}
    """

# TODO: Move Timer to util_nodes.py
class CyclistTimer:
    """Measures the time of the last generation, and sum of them all during session"""

    @classmethod
    def INPUT_TYPES(s):
        return { "required":{ "loop_id": ("STRING", {"default": DEFAULT_LOOP_ID}),
                              "mode": (["hours", "minutes", "seconds", "milliseconds"], {"default" : "seconds"})} }
    
    RETURN_TYPES = ("FLOAT", "FLOAT")
    RETURN_NAMES = ("last gen time", "total loop time")
    FUNCTION = "run"
    CATEGORY = "cyclist/Utilities"

    #NODE_NAME = "Generation Timer"

    def run(self, loop_id, mode):
        last, total = LoopTimer.getLoopTimer(loop_id).getIntervals()
        
        if (mode == "hours"):
            last = last / 3600
            total = total / 3600
        elif (mode == "minutes"):
            last = last / 60
            total = total / 60
        elif (mode == "milliseconds"):
            last = last * 1000
            total = total * 1000
        PromptServer.instance.send_sync("cyclist.timer.update", {"loop_id": loop_id, "last_time" : last, "total_time": total, "mode": mode})
        return (last, total)

    @classmethod
    def IS_CHANGED(self, loop_id, mode):
        LoopTimer.getLoopTimer(loop_id).reset()
        return float("NaN")

class CyclistTimerStop:
    """After getting any input, report a loop timer to finish measuring the time passed this loop"""

    @classmethod
    def INPUT_TYPES(s):
        return { "required":{ "any_in": (AnyType("*"), ), 
                              "loop_id": ("STRING", {"default": DEFAULT_LOOP_ID})}}
    
    RETURN_TYPES = ()
    FUNCTION = "stop"
    OUTPUT_NODE = True
    CATEGORY = "cyclist/Utilities"

    #NODE_NAME = "Force Timer Stop"

    def stop(self, any_in, loop_id):
        LoopTimer.getLoopTimer(loop_id).report_output_time(forceStop=True)
        return()

class LoopTimer:
    def __init__(self):
        self.start_time = 0.0
        self.last_interval = 0.0
        self.stored_interval = 0.0
        self.total_intervals = 0.0
        self.is_summed_this_run = False
        self.is_stopped_this_run = False
        self.is_force_stopped = False

    @classmethod
    def getLoopTimer(self, loop_id):
        if loop_id in cyclist_memory:
            if "LoopTimer" in cyclist_memory[loop_id]:
                return cyclist_memory[loop_id]["LoopTimer"]
        new_timer = LoopTimer()
        if not loop_id in cyclist_memory:
            cyclist_memory[loop_id] = {}
        cyclist_memory[loop_id]["LoopTimer"] = new_timer
        return new_timer

    def getIntervals(self):
        return_last = self.last_interval
        if not self.is_summed_this_run:
            self.total_intervals += self.last_interval
            if self.is_stopped_this_run:
                # Rare case: Something was saved before Timer procs
                return_last = self.stored_interval
                self.last_interval = self.stored_interval
            self.is_summed_this_run = True
        return (return_last, self.total_intervals)

    def reset(self):
        self.is_summed_this_run = False
        self.is_stopped_this_run = False
        self.is_force_stopped = False
        self.start_time = time.perf_counter()

    def report_output_time(self, forceStop = False):
        self.is_stopped_this_run = True
        if not self.is_force_stopped:
            if self.is_summed_this_run:
                self.last_interval = time.perf_counter() - self.start_time
            else:
                # Rare case: Something was saved before Timer procs
                self.stored_interval = time.perf_counter() - self.start_time
        self.is_force_stopped = forceStop