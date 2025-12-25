from langchain_core.messages import HumanMessage, AIMessage
from src.core.utils.llm_safety import (
    is_token_limit_exceeded,
    remove_up_to_last_ai_message,
)


# Mock Exceptions
class MockOpenAIError(Exception):
    def __init__(self, message, code=None, body=None):
        self.message = message
        self.code = code
        self.body = body
        super().__init__(message)


class ResourceExhausted(Exception):
    pass


class GoogleGenerativeAIFetchError(Exception):
    pass


class TestTokenGuard:
    def setup_method(self):
        # Configure Mocks to look like real library exceptions
        ResourceExhausted.__module__ = "google.api_core.exceptions"
        GoogleGenerativeAIFetchError.__module__ = "google.generativeai.types"

    def test_openai_token_limit(self):
        # Case 1: Keyword match
        err = MockOpenAIError("This model's maximum context length is 4097 tokens.")
        assert is_token_limit_exceeded(err, "openai:gpt-4") is True

        # Case 2: Error code in attribute
        err_code = MockOpenAIError("Error", code="context_length_exceeded")
        assert is_token_limit_exceeded(err_code, "openai:gpt-4") is True

        # Case 2b: Error code in body dict
        err_body = MockOpenAIError("Error", body={"code": "context_length_exceeded"})
        assert is_token_limit_exceeded(err_body, "openai:gpt-4") is True

        # Case 3: False positive check
        err_other = MockOpenAIError("Rate limit exceeded")
        assert is_token_limit_exceeded(err_other, "openai:gpt-4") is False

    def test_anthropic_token_limit(self):
        # Define class with correct name
        class BadRequestError(Exception):
            pass

        BadRequestError.__module__ = "anthropic"

        # Case 1: Prompt too long
        err = BadRequestError("anthropic: prompt is too long")
        assert is_token_limit_exceeded(err, "anthropic:claude-3") is True

        # Case 2: Max context length
        err2 = BadRequestError("maximum context length exceeded")
        assert is_token_limit_exceeded(err2, "anthropic:claude-3") is True

        err_other = BadRequestError("anthropic: overladen")
        assert is_token_limit_exceeded(err_other, "anthropic:claude-3") is False

    def test_gemini_token_limit(self):
        self.setup_method()  # Ensure mocks are configured

        # Case 1: ResourceExhausted Class with correct module
        # is_google_exception -> True (module has google)
        # is_resource_exhausted -> True (class name)
        err = ResourceExhausted("429 Resource has been exhausted")
        assert is_token_limit_exceeded(err, "google:gemini-pro") is True

        # Case 2: String match fallback
        # FIXED: String must contain "resource exhausted" exactly as substring
        err_str = Exception("429 resource exhausted")
        # '429' and 'resource exhausted' in string
        assert is_token_limit_exceeded(err_str, "google:gemini-pro") is True

        # Case 3: False positive
        err_other = Exception("Some other error")
        assert is_token_limit_exceeded(err_other, "google:gemini-pro") is False

    def test_remove_up_to_last_ai_message(self):
        messages = [
            HumanMessage(content="Hi"),
            AIMessage(content="Hello"),
            HumanMessage(content="What's the meaning of life?"),
            AIMessage(content="42"),
            HumanMessage(content="Are you sure?"),
        ]

        # Should cut off before the *last* AI message ("42")
        # AI indices: 1 ("Hello"), 3 ("42")
        # Logic removes up to 3 (exclusive) -> keeps 0, 1, 2
        truncated = remove_up_to_last_ai_message(messages)

        assert len(truncated) == 3
        # truncated[0] = Hi
        # truncated[1] = Hello
        # truncated[2] = What's...
        assert truncated[-1].content == "What's the meaning of life?"
        assert isinstance(truncated[1], AIMessage)

        # Verify correctness
        assert len(messages) == 5
