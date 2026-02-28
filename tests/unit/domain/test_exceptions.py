"""Unit tests for domain exception hierarchy."""

from src.domain.exceptions import (
    AccountLockedError,
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    DomainError,
    ExternalServiceError,
    NotFoundError,
    RepositoryError,
    ValidationError,
)


class TestDomainError:
    def test_domain_error_str_returns_message(self) -> None:
        err = DomainError(message="internal detail", user_message="safe msg")
        assert str(err) == "internal detail"

    def test_domain_error_defaults(self) -> None:
        err = DomainError(message="something broke")
        assert err.user_message == "An error occurred"
        assert err.error_code == "INTERNAL_ERROR"
        assert err.additional_data == {}

    def test_domain_error_is_exception(self) -> None:
        err = DomainError(message="test")
        assert isinstance(err, Exception)

    def test_domain_error_additional_data(self) -> None:
        err = DomainError(message="test", additional_data={"key": "value"})
        assert err.additional_data == {"key": "value"}


class TestValidationError:
    def test_default_error_code(self) -> None:
        err = ValidationError(message="bad input", user_message="Invalid input")
        assert err.error_code == "VALIDATION_ERROR"

    def test_inherits_domain_error(self) -> None:
        err = ValidationError(message="bad input")
        assert isinstance(err, DomainError)


class TestNotFoundError:
    def test_default_error_code(self) -> None:
        err = NotFoundError(message="missing", user_message="Not found")
        assert err.error_code == "NOT_FOUND"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(NotFoundError, DomainError)


class TestConflictError:
    def test_default_error_code(self) -> None:
        err = ConflictError(message="dup", user_message="Already exists")
        assert err.error_code == "CONFLICT"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(ConflictError, DomainError)


class TestAuthenticationError:
    def test_default_error_code(self) -> None:
        err = AuthenticationError(message="bad token", user_message="Unauthorized")
        assert err.error_code == "AUTHENTICATION_FAILED"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(AuthenticationError, DomainError)


class TestAuthorizationError:
    def test_default_error_code(self) -> None:
        err = AuthorizationError(message="no perms", user_message="Access denied")
        assert err.error_code == "FORBIDDEN"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(AuthorizationError, DomainError)


class TestAccountLockedError:
    def test_default_error_code(self) -> None:
        err = AccountLockedError(message="locked", user_message="Account locked")
        assert err.error_code == "ACCOUNT_LOCKED"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(AccountLockedError, DomainError)


class TestRepositoryError:
    def test_default_error_code(self) -> None:
        err = RepositoryError(message="db fail", user_message="An unexpected error occurred")
        assert err.error_code == "REPOSITORY_ERROR"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(RepositoryError, DomainError)


class TestExternalServiceError:
    def test_default_error_code(self) -> None:
        err = ExternalServiceError(message="timeout", user_message="Service unavailable")
        assert err.error_code == "EXTERNAL_SERVICE_ERROR"

    def test_inherits_domain_error(self) -> None:
        assert issubclass(ExternalServiceError, DomainError)


class TestExceptionCanBeRaised:
    def test_all_exceptions_are_catchable_as_domain_error(self) -> None:
        exceptions = [
            ValidationError(message="v"),
            NotFoundError(message="n"),
            ConflictError(message="c"),
            AuthenticationError(message="a"),
            AuthorizationError(message="z"),
            AccountLockedError(message="l"),
            RepositoryError(message="r"),
            ExternalServiceError(message="e"),
        ]
        for exc in exceptions:
            try:
                raise exc
            except DomainError as caught:
                assert caught.message == exc.message
