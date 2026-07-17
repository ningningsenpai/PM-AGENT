"""RabbitMQ 文件详情解析消费者。"""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from app.project.context.detail_analysis.schemas import FileParsingEvent
from app.project.context.detail_analysis.service import FileDetailAnalysisService
from app.project.context.detail_analysis.settings import FileDetailAnalysisSettings

logger = logging.getLogger(__name__)


@dataclass
class FileDetailConsumerRuntime:
    connection: Any
    channel: Any

    async def close(self) -> None:
        await self.channel.close()
        await self.connection.close()


async def start_file_detail_consumer(
    settings: FileDetailAnalysisSettings,
) -> FileDetailConsumerRuntime:
    """启动有界预取的异步消费者；首次失败重投一次，再失败进入死信队列。"""
    try:
        import aio_pika
    except ImportError as exception:
        raise RuntimeError("已启用文件详情消费者，但未安装 aio-pika 依赖") from exception

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=settings.prefetch_count)
    exchange = await channel.declare_exchange(
        settings.exchange,
        aio_pika.ExchangeType.TOPIC,
        durable=True,
    )
    await channel.declare_queue("pm-agent.file-detail.parse.dlq.v1", durable=True)
    queue = await channel.declare_queue(
        settings.queue,
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": "pm-agent.file-detail.parse.dlq.v1",
        },
    )
    await queue.bind(exchange, routing_key=settings.routing_key)
    service = FileDetailAnalysisService(settings)

    async def consume(message: Any) -> None:
        try:
            event = FileParsingEvent.model_validate_json(message.body)
            await service.process(event)
            await message.ack()
        except Exception:
            logger.exception("文件详情解析消息处理失败，message_id=%s", message.message_id)
            if message.redelivered:
                await message.reject(requeue=False)
            else:
                await message.nack(requeue=True)

    await queue.consume(consume, no_ack=False)
    return FileDetailConsumerRuntime(connection=connection, channel=channel)
