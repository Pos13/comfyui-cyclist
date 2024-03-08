import sys
import logging
import math
import torch

class CyclistMathFloat:
    """Node for simple floating point math operations between two vars. Does not check if values are safe to math."""

    @classmethod
    def INPUT_TYPES(s):
        return { "required": { "operation": (["addition", "subtraction", "multiplication", "division", "exponentiation", "max", "min"],),
                              "float_1": ("FLOAT", {"default": 1.0, "min": -sys.float_info.max, "max": sys.float_info.max, "step": 0.01, "round": False, "display": "number"}),
                              "float_2": ("FLOAT", {"default": 1.0, "min": -sys.float_info.max, "max": sys.float_info.max, "step": 0.01, "round": False, "display": "number"})}}
    
    RETURN_TYPES = ("FLOAT", )
    FUNCTION = "calc"
    CATEGORY = "cyclist/Utilities"

    #NODE_NAME = "Float Math"

    def calc(self, operation, float_1, float_2):
        if operation == "addition":
            return (float_1 + float_2,)
        elif operation == "subtraction":
            return (float_1 - float_2,)
        elif operation == "multiplication":
            return (float_1 * float_2,)
        elif operation == "division":
            return (float_1 / float_2,)
        elif operation == "exponentiation":
            return (float_1 ** float_2,)
        elif operation == "max":
            if float_1 > float_2:
                return (float_1,)
            else:
                return (float_2,)
        elif operation == "min":
            if float_1 < float_2:
                return (float_1,)
            else:
                return (float_2,)
        else:
            raise Exception("Float math operation is not in the list")
            return (1.0,)

class CyclistMathInt:
    """Node for simple integer math operations between two vars. Does not check if values are safe to math. Works as python operations."""

    @classmethod
    def INPUT_TYPES(s):
        return { "required": { "operation": (["addition", "subtraction", "multiplication", "floor division", "modulo", "exponentiation", "max", "min"],),
                              "int_1": ("INT", {"default": 1, "min": -sys.maxsize, "max": sys.maxsize}),
                              "int_2": ("INT", {"default": 1, "min": -sys.maxsize, "max": sys.maxsize})}}
    
    RETURN_TYPES = ("INT", )
    FUNCTION = "calc"
    CATEGORY = "cyclist/Utilities"

    #NODE_NAME = "Int Math"

    def calc(self, operation, int_1, int_2):
        if operation == "addition":
            return (int_1 + int_2,)
        elif operation == "subtraction":
            return (int_1 - int_2,)
        elif operation == "multiplication":
            return (int_1 * int_2,)
        elif operation == "floor division":
            return (int_1 // int_2,)
        elif operation == "modulo":
            return (int_1 % int_2,)
        elif operation == "exponentiation":
            return (int_1 ** int_2,)
        elif operation == "max":
            if int_1 > int_2:
                return (int_1,)
            else:
                return (int_2,)
        elif operation == "min":
            if int_1 < int_2:
                return (int_1,)
            else:
                return (int_2,)
        else:
            raise Exception("Int math operation is not in the list")
            return (0,)

# 'required' input can't be '*', unless it can. Thanks, @pythongossss
class AnyType(str):
    def __ne__(self, __value: object) -> bool:
        return False

class CyclistTypeCast:
    """Tries to cast any input into str, int, float and bool. Int returns mathematically rounded. Float and int return None on fails."""

    @classmethod
    def INPUT_TYPES(s):
        return {"required": {"anything": (AnyType("*"), )}}
    
    RETURN_TYPES = ("STRING", "INT", "FLOAT", "BOOLEAN")
    FUNCTION = "cast"
    CATEGORY = "cyclist/Utilities"

    #NODE_NAME = "Convert to"

    def cast(self, anything):
        res_str, res_int, res_float, res_bool = my_cast(anything)
        if res_int is None:
            logging.warn(f"Can't cast {type(anything)} to int")
        if res_float is None:
            logging.warn(f"Can't cast {type(anything)} to float")
        return res_str, res_int, res_float, res_bool

def my_cast(anything):
    try:
        result_float = float(anything)
        result_int = int(round(result_float))
    except:
        result_float = None
        result_int = None
    try:
        result_bool = bool(anything)
    except:
        if anything is None:
            result_bool = False
        else:
            result_bool = True
    return (str(anything), result_int, result_float, result_bool)

class CyclistCompare:
    """Tries to compare any two inputs. If different types provided, they would be cast to equal types. Order of prefered casts: bool, float, str."""

    @classmethod
    def INPUT_TYPES(s):
        return { "required": {"condition": (["equals", "not equals", "greater than", "less than", "greater or equals", "less or equals"],),
                              "thing1": (AnyType("*"), ),
                              "thing2": (AnyType("*"), )}}
    
    RETURN_TYPES = ("BOOLEAN", )
    FUNCTION = "compare"
    CATEGORY = "cyclist/Utilities"

    #NODE_NAME = "Compare Anything"

    def compare(self, condition, thing1, thing2):
        str1, int1, float1, bool1 = my_cast(thing1)
        str2, int2, float2, bool2 = my_cast(thing2)
        if torch.is_tensor(thing1):
            tensor1 = thing1
        elif isinstance(thing1, dict) and "samples" in thing1 and torch.is_tensor(thing1["samples"]):
            tensor1 = thing1["samples"]
        else:
            tensor1 = None
        if torch.is_tensor(thing2):
            tensor2 = thing2
        elif isinstance(thing2, dict) and "samples" in thing2 and torch.is_tensor(thing2["samples"]):
            tensor2 = thing2["samples"]
        else:
            tensor2 = None

        if isinstance(thing1, bool) or isinstance(thing2, bool):
            return (self.compare_bool(bool1, bool2, condition), )
        elif isinstance(thing1, str) or isinstance(thing2, str):
            if not float1 is None and not float2 is None:
                return (self.compare_float(float1, float2, condition), )
            else:
                return (self.compare_str(str1, str2, condition), )
        elif isinstance(thing1, float) or isinstance(thing2, float):
            return (self.compare_float(float1, float2, condition), )
        elif isinstance(thing1, int) and isinstance(thing2, int):
            return (self.compare_int(int1, int2, condition), )
        elif not tensor1 is None and not tensor2 is None:
            if (tensor1.dim() == 4 and tensor1.size()[1] != 4) or (tensor2.dim() == 4 and tensor2.size()[1] != 4):
                return (self.compare_tensors(tensor1, tensor2, condition, as_images=True), ) # Assume at least one is image
            else:
                return (self.compare_tensors(tensor1, tensor2, condition), )
        else:
            try:
                if condition == "equals":
                    result = thing1 == thing2
                elif condition == "not equals":
                    result = thing1 != thing2
                elif condition == "greater than":
                    result = thing1 > thing2
                elif condition == "less than":
                    result = thing1 < thing2
                elif condition == "greater or equals":
                    result = thing1 >= thing2
                elif condition == "less or equals":
                    result = thing1 <= thing2
                else:
                    raise Exception("Compare operation is not in the list")
                if not isinstance(result, bool):
                    raise Exception("Comparison ends in a non-boolean return")
                return (result, )
            except:
                logging.warn("'Compare Anything' node doesn't really know how to compare these inputs, so it falls back to compare string representations.")
                return (self.compare_str(str1, str2, condition), )
    
    def compare_bool(self, a, b, condition):
        if condition == "equals":
            return a == b
        elif condition == "not equals":
            return a != b
        elif condition == "greater than":
            return a == True and b == False
        elif condition == "less than":
            return a == False and b == True
        elif condition == "greater or equals":
            return True
        elif condition == "less or equals":
            return True
        else:
            raise Exception("Compare operation is not in the list")
    
    def compare_str(self, a, b, condition):
        if condition == "equals":
            return a == b
        elif condition == "not equals":
            return a != b
        elif condition == "greater than":
            return a > b
        elif condition == "less than":
            return a < b
        elif condition == "greater or equals":
            return a >= b
        elif condition == "less or equals":
            return a <= b
        else:
            raise Exception("Compare operation is not in the list")
    
    def compare_float(self, a, b, condition):
        if condition == "equals":
            return math.isclose(a, b)
        elif condition == "not equals":
            return not math.isclose(a, b)
        elif condition == "greater than":
            return a > b
        elif condition == "less than":
            return a < b
        elif condition == "greater or equals":
            return a >= b or math.isclose(a, b)
        elif condition == "less or equals":
            return a <= b or math.isclose(a, b)
        else:
            raise Exception("Compare operation is not in the list")
    
    def compare_int(self, a, b, condition):
        if condition == "equals":
            return a == b
        elif condition == "not equals":
            return a != b
        elif condition == "greater than":
            return a > b
        elif condition == "less than":
            return a < b
        elif condition == "greater or equals":
            return a >= b
        elif condition == "less or equals":
            return a <= b
        else:
            raise Exception("Compare operation is not in the list")
    
    def compare_tensors(self, a, b, condition, as_images=False):
        if condition == "equals":
            return torch.equal(a, b)
        elif condition == "not equals":
            return not torch.equal(a, b)
        else:
            size1 = 1
            if as_images:
                all_sizes1 = a.size()[:3] # Only comparing pixels count, not channels count
            else:
                all_sizes1 = a.size()
            for i in all_sizes1:
                size1 *= i
            size2 = 1
            if as_images:
                all_sizes2 = b.size()[:3] # Only comparing pixels count, not channels count
            else:
                all_sizes2 = b.size()
            for i in all_sizes2:
                size2 *= i
            
            if condition == "greater than":
                return size1 > size2
            elif condition == "less than":
                return size1 < size2
            elif condition == "greater or equals":
                return size1 > size2 or torch.equal(a, b)
            elif condition == "less or equals":
                return size1 < size2 or torch.equal(a, b)
            else:
                raise Exception("Compare operation is not in the list")