from pydantic import BaseModel


class CnpjApiResponse(BaseModel):
    descricao_situacao_cadastral: str
    data_inicio_atividade: str
    capital_social: float


class CnpjData(BaseModel):
    cnpj: str
    status: str
    company_age: float
    capital_stock: float
