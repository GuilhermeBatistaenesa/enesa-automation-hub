from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class IdentityContext:
    subject: str
    auth_source: str
    email: str | None = None
    external_object_id: str | None = None


class IdentityProvider(Protocol):
    """
    Contrato para provedores de identidade.
    Mantém o backend preparado para integrar Azure AD sem refatorar endpoints.
    """

    def resolve_identity(self, token: str) -> IdentityContext:
        ...


class LocalIdentityProvider:
    auth_source = "local"

    def resolve_identity(self, token: str) -> IdentityContext:
        return IdentityContext(subject=token, auth_source=self.auth_source)


class AzureADIdentityProvider:
    auth_source = "azure_ad"

    def resolve_identity(self, token: str) -> IdentityContext:
        raise NotImplementedError("Integração Azure AD será conectada nesta implementação via OIDC/JWKS.")

