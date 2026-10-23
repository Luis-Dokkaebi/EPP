import sys
import os

# Add src to path to import FaceRecognizer
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
src_dir = os.path.join(root_dir, 'src')
sys.path.append(src_dir)

from src.recognition.face_recognizer import FaceRecognizer

def main():
    if len(sys.argv) < 3:
        print("Usage: python utils/register_face.py <image_path> <name>")
        return

    image_path = sys.argv[1]
    name = sys.argv[2]
    
    if not os.path.exists(image_path):
        print(f"Error: Image file '{image_path}' not found.")
        return

    # Use absolute paths relative to project root
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    faces_dir = os.path.join(root_dir, 'data', 'faces')
    encodings_file = os.path.join(faces_dir, 'encodings.pkl')

    recognizer = FaceRecognizer(faces_dir=faces_dir, encodings_file=encodings_file)
    success = recognizer.register_face(image_path, name)
    
    if success:
        print(f"Successfully registered {name}.")
    else:
        print("Failed to register face.")

if __name__ == "__main__":
    main()
