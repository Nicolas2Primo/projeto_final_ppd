import pika
import json

class RabbitMQHandler:
    def __init__(self, amqp_url):
        self.connection_params = pika.URLParameters(amqp_url)

    def publish_message(self, receiver, sender, text):
        connection = pika.BlockingConnection(self.connection_params)
        channel = connection.channel()
        queue_name = f'queue_{receiver}'
        channel.queue_declare(queue=queue_name, durable=True)
        message_body = json.dumps({"sender": sender, "text": text})
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=message_body,
            properties=pika.BasicProperties(delivery_mode=2)
        )
        connection.close()

    def consume_messages(self, username, deliver_callback):
        """
        Busca mensagens uma a uma. Para cada mensagem, chama deliver_callback(message)
        que deve retornar True se a mensagem foi entregue (ou seja, o remetente está em range)
        ou False se não. Se não for entregue, a mensagem é requeue.
        """
        connection = pika.BlockingConnection(self.connection_params)
        channel = connection.channel()
        queue_name = f'queue_{username}'
        channel.queue_declare(queue=queue_name, durable=True)
        
        while True:
            method_frame, properties, body = channel.basic_get(queue=queue_name, auto_ack=False)
            if method_frame:
                message = json.loads(body)
                delivered = deliver_callback(message)
                if delivered:
                    channel.basic_ack(delivery_tag=method_frame.delivery_tag)
                else:
                    channel.basic_nack(delivery_tag=method_frame.delivery_tag, requeue=True)
            else:
                break
        connection.close()
