import requests
from utils.logger import Logger

class SlackNotifier:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.logger = Logger.get_logger("eks-update")

    def send_block_message(self, blocks: list) -> bool:
        payload = {"blocks": blocks}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code == 200:
                self.logger.info("Slack message sent successfully")
                return True
            else:
                self.logger.error(
                    f"Slack message failed: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            self.logger.error(f"Error sending slack message: {str(e)}")
            return False

    def _format_table(self, headers, rows):
        if not rows:
            return ""
        
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))
        
        lines = []
        
        header_line = " | ".join(
            str(h).ljust(col_widths[i]) for i, h in enumerate(headers)
        )
        lines.append(header_line)
        
        separator = "-+-".join("-" * w for w in col_widths)
        lines.append(separator)
        
        for row in rows:
            row_line = " | ".join(
                str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)
            )
            lines.append(row_line)
        
        return "\n".join(lines)

    def send_report(self, report):
        total = len(report.records)
        needs_update = sum(1 for r in report.records if r.get("Needs Update"))
        triggered = len(report.triggered_updates)
        account_names = sorted(
            {item.get("Account Name", "") for item in report.records if item.get("Account Name")}
        )

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "EKS Managed Nodegroup AMI Update Summary"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Total Checked:* {total}     |     *Needs Update:* {needs_update}     |     *Updates Triggered:* {triggered}"
                }
            }
        ]

        if account_names:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Account Name(s):* {', '.join(account_names)}"
                        }
                    ]
                }
            )

        if report.triggered_updates:
            headers = ["Account Name", "Region", "Cluster", "Nodegroup", "Update ID"]
            table_rows = []
            
            for item in report.triggered_updates:
                table_rows.append([
                    item.get('Account Name', ''),
                    item['Region'],
                    item['Cluster'],
                    item['Nodegroup'],
                    item['Update ID']
                ])
            
            table_str = self._format_table(headers, table_rows)
            
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Triggered Updates*\n```\n{table_str}\n```"
                }
            })

        self.send_block_message(blocks)
        