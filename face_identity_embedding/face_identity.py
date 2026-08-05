import uuid
import numpy as np
import torch
from PIL import Image

from torchvision import transforms
from facenet_pytorch import InceptionResnetV1


from memory.database import get_connection

SIMILARITY_THRESHOLD = 0.7
_embedder = None

def get_embedder():
    global _embedder
    if _embedder is None:
        _embedder = InceptionResnetV1(pretrained='vggface2').eval()
    return _embedder

def compute_embedding(face_crop_rgb):
    image = Image.fromarray(face_crop_rgb)
    transform = transforms.Compose([
        transforms.Resize((160,160)),
        transforms.ToTensor(),
    ])
    tensor = transform(image).unsqueeze(0)
    with torch.no_grad():
        embedding_tensor = get_embedder()(tensor)

    return embedding_tensor[0].numpy()

def cosine_similarity(a, b):
    return float(np.dot(a,b))


def load_known_person():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT id, embedding FROM persons")
    results = []
    for row in cursor.fetchall():
        person_id, embedding_blob = row
        embedding_array = np.frombuffer(embedding_blob, dtype=np.float32)
        results.append((person_id, embedding_array))
    connection.close()
    return results

def enroll_new_person(embedding):
    person_id = str(uuid.uuid4())
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("INSERT INTO persons (id, embedding)VALUES (?,?)", (person_id, embedding.tobytes()))
    connection.commit()
    connection.close()
    return person_id

def find_or_enroll_person(face_crop_rgb):
    embedding = compute_embedding(face_crop_rgb)
    known_person = load_known_person()

    best_match_id = None
    highest_similarity = SIMILARITY_THRESHOLD
    for person_id, known_embedding in known_person:
        similarity = cosine_similarity(embedding, known_embedding)
        if similarity > highest_similarity:
            highest_similarity = similarity
            best_match_id = person_id
    if best_match_id is not None:
            return best_match_id
    return enroll_new_person(embedding)



