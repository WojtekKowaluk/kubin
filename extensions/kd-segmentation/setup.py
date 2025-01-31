import os
import gradio as gr
import torch
from PIL import Image
import numpy as np
import urllib.request
from segment_anything import SamPredictor, SamAutomaticMaskGenerator, sam_model_registry

def setup(kubin):
  source_image = gr.Image(type='pil', label='Image to extract mask from', elem_classes=['full-height'])

  def segment_anything_ui(ui_shared, ui_tabs):
    selected_mask_index = gr.State(None) # type: ignore

    with gr.Row() as segment_block:
      with gr.Column(scale=1):
        with gr.Row():
          source_image.render()

      with gr.Row():
        model_type = gr.Radio(choices=['vit_h/sam_vit_h_4b8939', 'vit_l/sam_vit_l_0b3195', 'vit_b/sam_vit_b_01ec64.pth'], value='vit_h/sam_vit_h_4b8939', label='Model type')

      with gr.Row(visible=False):
        prompt = gr.Textbox('', label='Prompt', placeholder='')

      with gr.Column(scale=2):
        segment_btn = gr.Button('Segment image', variant='primary')
        segment_output = gr.Gallery(label='Segmented Masks').style(preview=True, grid=4)
        
        ui_shared.create_base_send_targets(segment_output, selected_mask_index, ui_tabs) 

      def select_point(img, evt: gr.SelectData):
        selected_point = img[evt.index[1], evt.index[0]] # type: ignore
        print(evt)
        print(f"Selected point: {selected_point}")
      
      source_image.select(select_point, source_image)

      segment_btn.click(fn=lambda *p: segment_image(kubin, *p), inputs=[
        source_image,
        prompt,
        model_type,
        gr.State(kubin.args.cache_dir), # type: ignore
        gr.State(kubin.args.device) # type: ignore
      ], outputs=segment_output)

    return segment_block
  
  return {
    'title': 'Image Segmentation',
    'tab_fn': lambda ui_s, ts: segment_anything_ui(ui_s, ts),
    'send_target': source_image
  } 

def segment_image(kubin, source_image, prompt, model, cache_dir, device):
  model_path = f'{cache_dir}/SAM'
  if not os.path.exists(model_path): os.makedirs(model_path)

  type, checkpoint = model.split('/')
  if type == 'vit_h':
    model_url, download_path  = 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_h_4b8939.pth', f'{model_path}/sam_vit_h_4b8939.pth'
  elif type == 'vit_l':
    model_url, download_path = 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_l_0b3195.pth', f'{model_path}/sam_vit_l_0b3195.pth'
  else:
    model_url, download_path = 'https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth', f'{model_path}/sam_vit_b_01ec64.pth'

  if not os.path.exists(download_path):
    print(f'downloading model {model_url} to {download_path}')
    urllib.request.urlretrieve(model_url, download_path)
    print('model downloaded')

  sam = sam_model_registry[type](checkpoint=download_path)
  sam.to(device=device)
  np_array = np.array(source_image)

  if prompt == '':
    mask_generator = SamAutomaticMaskGenerator(sam)
    masks = mask_generator.generate(np_array)
  else:
    predictor = SamPredictor(sam)
    predictor.set_image(np_array)
    masks, _, _ = predictor.predict(prompt)
    
  if len(masks) == 0:
    return []
  
  sorted_masks = sorted(masks, key=(lambda x: x['area']), reverse=True)

  images = []
  for ann in sorted_masks:
    m = ann['segmentation']
    img = np.zeros((m.shape[0], m.shape[1]), dtype=np.uint8)
    img[m > 0] = 255

    images.append(Image.fromarray(img))
    images.append(Image.fromarray(255 - img)) # also include inverted version

  return images