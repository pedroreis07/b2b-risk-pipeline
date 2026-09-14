# B2B Risk Pipeline

A data pipeline for risk analysis of B2B financial transactions.

---

## The Challenge

Process batches of financial transactions under constrained hardware limits, fulfilling the following requirements:

- Ingest continuous transaction batches delivered in Parquet format.
- Enrich CNPJ data via the [Minha Receita](https://docs.minhareceita.org/) API.
- Evaluate transactions and apply penalty points based on risk rules.
- Run within the strict CPU, memory, and network limits defined below.

> **Note:** The minimum execution time and the specific batch files to be used for the test are not defined yet.

---

## Hardware and Network Constraints

### 1. Worker
* **Compute:** 2 vCPUs, 1 GB RAM.
* **Storage:** 3,000 IOPS, 125 MB/s throughput.

### 2. Database
* **Compute:** 2 vCPUs, 1 GB RAM, 256 MB `shared_buffers`.
* **Storage:** 3,000 IOPS, 125 MB/s throughput.

### 3. Cache
* **Compute:** 2 vCPUs, 0.5 GB RAM.
* **Storage:** 100% in-memory.

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
