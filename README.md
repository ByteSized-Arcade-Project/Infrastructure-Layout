# ByteSized Arcade – Retro Web-Game Platform with Async High-Score Validation

## 🚀 Project Overview
A production-grade, cost-optimized AWS architecture built for an indie gaming platform to handle viral high-score traffic surges asynchronously using decoupled cloud services.

## 🏗️ Architecture Diagram
[Insert your draw.io / Lucidchart architecture diagram here]

## 🛠️ Tech Stack & Service Breakdown
* **Frontend:** HTML5/JavaScript game hosted on Nginx via **Amazon EC2** in an Auto Scaling Group behind an **Application Load Balancer (ALB)**.
* **Messaging Queue:** **Amazon SQS** handles high-volume ingest to throttle database writes and prevent service degradation.
* **Compute / Validation:** **AWS Lambda** sanitizes score payloads and executes secure inputs.
* **Database:** **Amazon RDS (MySQL)** deployed in isolated private subnets for persistent data storage.
* **Security:** Layered security groups, private-subnet isolation, and custom **Network ACLs (NACLs)**.

## 👥 Individual Contributions
* **[Name 1] (Project Lead):** ...
* **[Name 2] (Infrastructure Engineer):** ...
* **[Name 3] (Security & IAM Lead):** ...
