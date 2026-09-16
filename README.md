# B2B Risk Pipeline

High-performance data pipeline for risk analysis of B2B financial transactions under constrained hardware limits:

- Ingest continuous transaction batches delivered in Parquet format.
- Enrich CNPJ data via the [Minha Receita](https://docs.minhareceita.org/) API.
- Evaluate transactions and apply penalty points based on risk rules.
- Run within strict CPU, memory, and storage limits.

> **Note:** The minimum execution time and the specific batch files to be used for the test are not defined yet.

---

## Tools

- **Language & Runtime:** Python 3.13, uv
- **Data Processing:** Polars, DuckDB, PyArrow
- **Database:** PostgreSQL 18
- **Cache:** Redis 8
- **Containerization:** Docker, Docker Compose

---

## Getting Started

### Prerequisites

- Docker and Docker Compose

### Setup & Running

1. Set the disk path environment variable in `.env` for I/O throttling:
   ```bash
   echo "DOCKER_DISK_PATH=$(df /var/lib/docker | awk 'NR==2 {print $1}')" > .env
   ```

2. Place input Parquet files in `./data`:
   ```bash
   ls data/*.parquet
   ```

3. Run the pipeline:
   ```bash
   docker compose up --build
   ```

---

## Hardware and Network Constraints

### 1. Worker
* **Compute:** 2 vCPUs, 1 GB RAM, 1 GB Swap.
* **Storage:** 3,000 IOPS, 125 MB/s throughput.

### 2. Database
* **Compute:** 2 vCPUs, 1 GB RAM, 1 GB Swap.
* **Storage:** 3,000 IOPS, 125 MB/s throughput.

### 3. Cache
* **Compute:** 2 vCPUs, 0.5 GB RAM.
* **Storage:** 100% in-memory.

---

## Parquet File Structure

Input batch files follow this schema:

| Column | Type | Description |
| :--- | :--- | :--- |
| `transaction_id` | String | Unique transaction identifier |
| `event_timestamp` | String | Timestamp in ISO 8601 format |
| `payer_cnpj` | String | 14-digit CNPJ of the payer |
| `receiver_cnpj` | String | 14-digit CNPJ of the receiver |
| `invoice_id` | String | Associated invoice identifier |
| `amount` | Float64 | Transaction amount |
| `payment_method` | String | Payment method (e.g., PIX, TED, BOLETO) |
| `due_date` | Date | Due date (`YYYY-MM-DD`) |
| `description` | String | Transaction description |

---

## Minha Receita API

Enriches payer and receiver CNPJ metadata (`GET https://minhareceita.org/{cnpj}`). Only the following fields are consumed:

```json
{
  "descricao_situacao_cadastral": "ATIVA",
  "data_inicio_atividade": "2007-12-20",
  "capital_social": 100000.0
}
```

---

## Risk Scoring

| Condition | Points | Reason Code |
| :--- | :---: | :--- |
| Same `transaction_id` submitted with diverging payload | **+75** | `payload_mutation_detected` |
| Payer CNPJ status is not `ATIVO` | **+50** | `payer_cnpj_inactive` |
| Receiver CNPJ status is not `ATIVO` | **+50** | `receiver_cnpj_inactive` |
| Transaction amount exceeds payer capital stock | **+20** | `amount_over_payer_capital` |
| Payer company founded less than 1 year ago | **+10** | `payer_less_than_1_year` |
| Receiver company founded less than 1 year ago | **+10** | `receiver_less_than_1_year` |
| Transaction amount exceeds R$ 100,000.00 | **+10** | `amount_over_100k` |

---

## Acknowledgments

Special thanks to [Eduardo Cuducos](https://bsky.app/profile/cuducos.me) for creating and maintaining the free, open-source [Minha Receita](https://docs.minhareceita.org/) API.
