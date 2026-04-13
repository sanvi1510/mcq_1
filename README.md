# Project Title
PDF Quiz Generator

## Description
This project is a web application that generates quizzes from PDF files. It uses natural language processing (NLP) and machine learning (ML) to extract questions and answers from the PDF content. The application provides a user-friendly interface for uploading PDF files, configuring quiz settings, and generating quizzes.

## Installation
To install the project, follow these steps:

1. Clone the repository: `git clone https://github.com/your-repo/pdfs-quiz-generator.git`
2. Install the required packages: `pip install -r requirements.txt`
3. Set the `GROQ_API_KEY` environment variable: `export GROQ_API_KEY=your_api_key`
4. Run the application: `python app.py`

## Usage Examples
Here are some examples of how to use the application:

### Generating a Quiz
To generate a quiz, follow these steps:

1. Upload a PDF file using the file input element.
2. Configure the quiz settings, such as the number of questions and difficulty level.
3. Click the "Generate Quiz" button to generate the quiz.

### Example Code
Here is an example of how to generate a quiz using the application's API:
```python
import requests

# Replace with your API endpoint URL
url = 'http://localhost:5000/generate-quiz'

# Replace with your PDF file
with open('example.pdf', 'rb') as pdf_file:
    # Replace with your quiz settings
    num_questions = 5
    difficulty = 'Medium'

    # Send the request
    response = requests.post(url, files={'file': pdf_file}, data={'num_questions': num_questions, 'difficulty': difficulty})

    # Print the response
    print(response.json())
```
Note: Make sure to replace the `url` variable with the actual URL of your API endpoint.

### API Reference
The application provides the following API endpoints:

* `GET /`: Returns the index page.
* `POST /generate-quiz`: Generates a quiz from a PDF file.
* `GET /health`: Returns the health status of the application.

## License
This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).