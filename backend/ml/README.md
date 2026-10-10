# Custom ML component: interview-question classifier

## What it does
Predicts an interview question's **type** (`technical`, `hr`, `behavioral`, `communication`, `project`)
from its text. Every AI-generated interview question stores the prediction in `InterviewQuestion.meta.classifier`,
so a mismatch between what the language model claimed and what the classifier sees can be reviewed.
It is a cross-check only: it never changes the interview.

## Why this component (and not others)
| Candidate | Decision |
|---|---|
| Question **type** classification | **Built and deployed.** Short texts with clear wording patterns; a labelled set could be written. |
| Question **difficulty** classification | **Built, evaluated, NOT deployed.** It did not beat a simple length/keyword rule (see below). Difficulty depends on the candidate and context, not only on wording. |
| Skill categorisation | Not built. The language model already returns categories, and the vocabulary is open-ended. A trained model needs far more labelled skills. |
| Predicting next difficulty | Not built. A transparent rule (score ≥ 75 → harder, < 45 → easier) is easier to explain and needs no data. |
| Recurring skill gaps | Not built. That is counting and aggregation, not prediction. |

## Data (development only)
* `data/interview_questions_dev.csv`: **176 questions written and labelled by hand for this project.** This is a
  development dataset, not real interview data, and the labels reflect one person's judgement.
* The 15 de-duplicated admin seed questions from `app/seed.py`.
* 191 questions in total. Type classes: technical 89, hr 34, behavioral 26, communication 22, project 20.

## Method
TF-IDF (word 1–2-grams + character 3–5-grams) → logistic regression (class-balanced).
* Stratified 75/25 hold-out split (seed 42) and 5-fold stratified cross-validation.
* Each target is compared with two baselines: always predicting the most common class, and a transparent keyword/length rule.
* **Deployment rule:** a model is saved only if it beats the keyword rule in cross-validation on **both** accuracy and macro-F1.
* After evaluation, the deployed model is refit on all the data.

## Results (2026-10-10)
| Target | Model | Hold-out acc | Hold-out macro-F1 | 5-fold CV acc | 5-fold CV macro-F1 |
|---|---|---|---|---|---|
| type | TF-IDF + LogReg | 0.917 | 0.881 | **0.885** | **0.845** |
| type | keyword rule | 0.854 | 0.836 | 0.848 | 0.829 |
| type | majority class | 0.458 | 0.126 | – | – |
| difficulty | TF-IDF + LogReg | 0.521 | 0.532 | 0.518 | 0.508 |
| difficulty | length/keyword rule | 0.396 | 0.371 | **0.524** | 0.500 |
| difficulty | majority class | 0.438 | 0.203 | – | – |

Full per-class reports and confusion matrices are in `models/metrics.json`.

## Limitations (please read)
* With only 48 test questions, one wrong prediction moves accuracy by about 2 points. The type model's lead over
  the keyword rule (+3.7 accuracy points in CV) is **small and not proven to be statistically significant**.
* The data is synthetic and written by one person, so these numbers **do not show production accuracy**. The
  model is not production-ready. Retrain it on real, independently labelled questions before relying on it.
* The most common type error is **communication → technical** (questions that explain a technical topic simply).

## Retrain
```powershell
cd backend
.\venv\Scripts\python.exe -m ml.train_question_classifier
```
Training never runs during web requests. The backend loads `models/question_classifier.joblib` once, on first use.
