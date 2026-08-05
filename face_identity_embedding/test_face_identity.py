from cv.picture import CVPipeline
from face_identity_embedding.face_identity import find_or_enroll_person

cv_pipeline = CVPipeline()
cv_pipeline.turn_on_camera()

emotions, face_rgb = cv_pipeline.execute()
if face_rgb is not None:
    person_id = find_or_enroll_person(face_rgb)
    print("person_id:", person_id)
else:
    print("no face detected")

cv_pipeline.turn_off_camera()