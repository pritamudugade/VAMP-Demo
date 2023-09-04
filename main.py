import glob
import streamlit as st
import wget
from PIL import Image
import torch
import cv2
import os
import time

st.set_page_config(layout="wide")

cfg_model_path = 'models/yolov5s.pt'
model = None
confidence = .25


def image_input(data_src):
    img_file = None
    if data_src == 'Sample data':
        # get all sample images
        img_path = glob.glob('data/sample_images/*')
        if img_path:
            img_slider = st.slider("Select a test image.", min_value=1, max_value=len(img_path), step=1)
            if 1 <= img_slider <= len(img_path):
                img_file = img_path[img_slider - 1]
            else:
                st.error("Invalid image selection.")
        else:
            st.error("please select the desired option")
    else:
        img_bytes = st.sidebar.file_uploader("Upload an image", type=['png', 'jpeg', 'jpg'])
        if img_bytes:
            img_file = "data/uploaded_data/upload." + img_bytes.name.split('.')[-1]
            Image.open(img_bytes).save(img_file)

    if img_file:
        col1, col2 = st.columns(2)
        with col1:
            st.image(img_file, caption="Selected Image")
        with col2:
            img = infer_image(img_file)
            st.image(img, caption="Model prediction")


def video_input(data_src):
    vid_file = None
    if data_src == 'Sample data':
        vid_file = "data/sample_videos/sample.mp4"
    else:
        vid_bytes = st.sidebar.file_uploader("Upload a video", type=['mp4', 'mpv', 'avi'])
        if vid_bytes:
            vid_file = "data/uploaded_data/upload." + vid_bytes.name.split('.')[-1]
            with open(vid_file, 'wb') as out:
                out.write(vid_bytes.read())

    if vid_file:
        cap = cv2.VideoCapture(vid_file)
        custom_size = st.sidebar.checkbox("Custom frame size")
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if custom_size:
            width = st.sidebar.number_input("Width", min_value=120, step=20, value=width)
            height = st.sidebar.number_input("Height", min_value=120, step=20, value=height)

        fps = 0
        st1, st2, st3 = st.columns(3)
        with st1:
            st.markdown("## Height")
            st1_text = st.markdown(f"{height}")
        with st2:
            st.markdown("## Width")
            st2_text = st.markdown(f"{width}")
        with st3:
            st.markdown("## FPS")
            st3_text = st.markdown(f"{fps}")

        st.markdown("---")
        output = st.empty()
        prev_time = 0
        curr_time = 0
        detected_objects = []

        while True:
            ret, frame = cap.read()
            if not ret:
                st.write("Can't read frame, stream ended? Exiting ....")
                break
            frame = cv2.resize(frame, (width, height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            output_img, objects = infer_image(frame, return_objects=True)
            output.image(output_img)
            curr_time = time.time()
            fps = 1 / (curr_time - prev_time)
            prev_time = curr_time
            st1_text.markdown(f"**{height}**")
            st2_text.markdown(f"**{width}**")
            st3_text.markdown(f"**{fps:.2f}**")

            # Collect detected objects
            detected_objects.extend(objects)

        cap.release()

        # Display the list of detected objects at the end
        st.write("Total Detected Objects:")
        for idx, obj in enumerate(detected_objects, start=1):
            st.write(f"{idx}. Label: {obj['label']}, Confidence: {obj['confidence']:.2f}, Bounding Box: {obj['bbox']}")




def infer_image(img, size=None, return_objects=False):
    model.conf = confidence
    result = model(img, size=size) if size else model(img)
    result.render()
    image = Image.fromarray(result.ims[0])

    if return_objects:
        detected_objects = []
        for label, conf, bbox in zip(result.names[0], result.pred[0][:, 4].tolist(), result.pred[0][:, :4].tolist()):
            detected_objects.append({
                'label': label,
                'confidence': conf,
                'bbox': bbox
            })
        return image, detected_objects

    return image


@st.cache_resource
def load_model(path, device):
    model_ = torch.hub.load('ultralytics/yolov5', 'custom', path=path, force_reload=True)
    model_.to(device)
    print("model to ", device)
    return model_


def load_custom_model(model_path, device):
    model = torch.load(model_path, map_location=device)
    model.eval()
    return model


@st.cache_resource
def download_model(url):
    model_file = wget.download(url, out="models")
    return model_file


def get_user_model():
    model_src = st.sidebar.radio("Model source", ["file upload", "url"])
    model_file = None
    if model_src == "file upload":
        model_bytes = st.sidebar.file_uploader("Upload a model file", type=['pt'])
        if model_bytes:
            model_file = "models/uploaded_" + model_bytes.name
            with open(model_file, 'wb') as out:
                out.write(model_bytes.read())
    else:
        url = st.sidebar.text_input("model url")
        if url:
            model_file_ = download_model(url)
            if model_file_.split(".")[-1] == "pt":
                model_file = model_file_

    return model_file

# Default values
default_input_option = 'video'
default_data_src = 'Upload data from the local system'



def main():
    # global variables
    global model, confidence, cfg_model_path

    # Center the headline
    st.markdown("<h1 style='text-align: center;'>Object Detection Webapp</h1>", unsafe_allow_html=True)

    st.sidebar.title("Custom settings")

    # upload model
    model_src = st.sidebar.radio("Select weight file", ["Custom model", "YOLO"])
    # URL, upload file (max 200 mb)
    if model_src == "Use your own model":
        user_model_path = get_user_model()
        if user_model_path:
            cfg_model_path = user_model_path

        st.sidebar.text(cfg_model_path.split("/")[-1])
        st.sidebar.markdown("---")

        # Load the custom model
        model = load_custom_model(cfg_model_path, 'cpu')

    # check if model file is available
    if not os.path.isfile(cfg_model_path):
        st.warning("Model file not available!!!, please add it to the model folder.", icon="⚠️")
    else:
        # Load the model using the selected device (CPU by default)
        model = load_model(cfg_model_path, 'cpu')

        # confidence slider
        confidence = st.sidebar.slider('Confidence', min_value=0.1, max_value=1.0, value=.45)

        # custom classes
        if st.sidebar.checkbox("Custom Classes"):
            model_names = list(model.names.values())
            assigned_class = st.sidebar.multiselect("Select Classes", model_names, default=[model_names[0]])
            classes = [model_names.index(name) for name in assigned_class]
            model.classes = classes
        else:
            model.classes = list(model.names.keys())

        st.sidebar.markdown("---")

        # input options
        input_option = st.sidebar.radio("Select input type: ", ['image', 'video'])

        # input src option
        data_src = st.sidebar.radio("Select input source: ", ['Sample data', 'Upload data from the local system'])

        if input_option == 'image':
            image_input(data_src)
        else:
            video_input(data_src)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        pass

# Add author details at the bottom
st.markdown("<br><br>", unsafe_allow_html=True)  # Create some space
st.markdown("<p style='text-align: center;'>Created by Your Name</p>", unsafe_allow_html=True)
