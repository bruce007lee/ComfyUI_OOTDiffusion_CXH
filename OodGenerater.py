import numpy as np
from PIL import Image
from torchvision.transforms.functional import to_pil_image, to_tensor

from .preprocess.openpose.run_openpose import OpenPose
from .preprocess.humanparsing.aigc_run_parsing import Parsing
from .ootd.inference_ootd_hd import OOTDiffusionHD
from .ootd.inference_ootd_dc import OOTDiffusionDC

from .utils_ootd import get_mask_location

cude_type = 0
openpose_model_hd = OpenPose(cude_type)
parsing_model_hd = Parsing(cude_type)
ootd_model_hd = OOTDiffusionHD(cude_type)

def tensor2pil(image):
    return Image.fromarray(np.clip(255. * image.cpu().numpy().squeeze(), 0, 255).astype(np.uint8))

def fitResize(image, size, cfg=None):
    nwidth, nheight = size
    width, height = image.size
    ratio = min([float(nwidth) / width, float(nheight) / height])
    return image.resize((int(width * ratio), int(height * ratio)), cfg)


category_dict_utils = ['upper_body', 'lower_body', 'dresses']

class Ood_hd_CXH:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "cloth_image": ("IMAGE",),
                "model_image": ("IMAGE",),
                "category":   (["upperbody","lowerbody","dress"],{"default":"upperbody"} ),
                "steps": ("INT", {"default": 20, "min": 20, "max": 40, "step": 1}),
                "scale": ("FLOAT", {"default":2, "min": 1, "max": 5, "step":0.1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),      
            }
        }

    RETURN_TYPES = ("IMAGE", "IMAGE")
    RETURN_NAMES = ("image", "image_masked")
    FUNCTION = "generate"

    CATEGORY = "CXH"

    def generate(self, cloth_image, model_image,category,steps,scale,seed):
        model_type = 'hd'
       
        vton_img= tensor2pil(model_image)
        # vton_img = vton_img.resize((768, 1024))
        vton_img = fitResize(vton_img, (768, 1024))

        mm_w,mm_h = vton_img.size

        garm_img = tensor2pil(cloth_image)
        # garm_img = garm_img.resize((768, 1024))
        garm_img = fitResize(garm_img, (mm_w, mm_h))
        garm_img =  garm_img.crop((0, 0, mm_w, mm_h))
        
        # keypoints = openpose_model_hd(vton_img.resize((384, 512)))
        # model_parse, _ = parsing_model_hd(vton_img.resize((384, 512)))
        preMask = fitResize(vton_img, (384, 512))
        preMask_w, preMask_h = preMask.size
        keypoints = openpose_model_hd(preMask)
        model_parse, _ = parsing_model_hd(preMask)
        
        dictype = 0
        if category == "upperbody":
            dictype = 0
        if category == "lowerbody":
            dictype = 1
        if category == "dress":
            dictype = 2    
        mask, mask_gray = get_mask_location(model_type, category_dict_utils[dictype], model_parse, keypoints, preMask_w, preMask_h)
        # mask = mask.resize((768, 1024), Image.NEAREST)
        # mask_gray = mask_gray.resize((768, 1024), Image.NEAREST)
        mask = fitResize(mask, (768, 1024), Image.NEAREST)
        mask_gray = fitResize(mask_gray, (768, 1024), Image.NEAREST)
        
        masked_vton_img = Image.composite(mask_gray, vton_img, mask)
        
        images = ootd_model_hd(
            model_type=model_type,
            category=category,
            image_garm=garm_img,
            image_vton=masked_vton_img,
            mask=mask,
            image_ori=vton_img,
            num_samples=1,
            num_steps=steps,
            image_scale=scale,
            seed=seed,
        )
        
        output_image = to_tensor(images[0])
        output_image = output_image.permute((1, 2, 0))
        masked_vton_img = masked_vton_img.convert("RGB")
        masked_vton_img = to_tensor(masked_vton_img)
        masked_vton_img = masked_vton_img.permute((1, 2, 0))
        return ([output_image], [masked_vton_img])


