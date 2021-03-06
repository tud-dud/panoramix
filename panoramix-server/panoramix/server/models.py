from django.db import models

import datetime

from panoramix import spec

get_now = datetime.datetime.utcnow


def to_choices(named):
    values = list(named)
    return [(value, value) for value in values]


class Negotiation(models.Model):
    id = models.CharField(max_length=255, primary_key=True)
    text = models.TextField(null=True)
    status = models.CharField(
        max_length=255, choices=to_choices(spec.NegotiationStatus),
        default=spec.NegotiationStatus.OPEN)
    timestamp = models.DateTimeField(null=True)
    consensus = models.CharField(max_length=255, null=True, unique=True)

    def get_latest_contributions(self):
        return Contribution.objects.filter(latest=True, negotiation=self)

    def get_text_and_signatures(self, contributions):
        texts = set(c.text for c in contributions)
        assert len(texts) == 1
        text = texts.pop()
        signings = dict((c.signer_key_id, c.signature)
                        for c in contributions)
        return {
            "text": text,
            "signings": signings,
        }

    def to_consensus_dict(self):
        contributions = self.get_latest_contributions()
        d = {}
        d.update(self.get_text_and_signatures(contributions))
        d["id"] = self.consensus
        d["negotiation_id"] = self.id
        d["timestamp"] = self.timestamp
        return d


class Signing(models.Model):
    negotiation = models.ForeignKey(Negotiation, related_name="signings")
    signer_key_id = models.CharField(max_length=255)
    signature = models.TextField()


class Contribution(models.Model):
    negotiation = models.ForeignKey(Negotiation, related_name="contributions")
    text = models.TextField()
    latest = models.BooleanField()
    signer_key_id = models.CharField(max_length=255)
    signature = models.TextField()

    class Meta:
        index_together = ["negotiation", "signer_key_id"]


class Peer(models.Model):
    name = models.CharField(max_length=255)
    peer_id = models.CharField(max_length=255, primary_key=True)
    key_type = models.IntegerField()
    crypto_backend = models.CharField(max_length=255)
    crypto_params = models.TextField()
    key_data = models.TextField(unique=True)
    status = models.CharField(
        max_length=255, choices=to_choices(spec.PeerStatus))

    def log_consensus(self, consensus_id):
        self.consensus_logs.create(
            consensus_id=consensus_id,
            status=self.status,
            timestamp=get_now())

    def list_owners(self):
        owners = self.owners.all()
        return [owner.show() for owner in owners]


class PeerConsensusLog(models.Model):
    peer = models.ForeignKey(Peer, related_name="consensus_logs")
    consensus_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    status = models.CharField(
        max_length=255, choices=to_choices(spec.PeerStatus))

    class Meta:
        index_together = ["peer", "id"]


class Owner(models.Model):
    peer = models.ForeignKey(Peer, related_name='owners')
    owner_key_id = models.CharField(max_length=255)

    class Meta:
        unique_together = ["peer", "owner_key_id"]

    def show(self):
        return self.owner_key_id


class Endpoint(models.Model):
    endpoint_id = models.CharField(max_length=255, primary_key=True)
    peer_id = models.CharField(max_length=255, db_index=True)
    description = models.CharField(max_length=255)
    public = models.IntegerField()
    size_min = models.IntegerField()
    size_max = models.IntegerField()
    endpoint_type = models.CharField(max_length=255)
    endpoint_params = models.TextField()

    # size_current = models.IntegerField(default=0)
    # messages_total = models.IntegerField(default=0)  # what is total?
    # messages_sent = models.IntegerField(default=0)
    # messages_processed = models.IntegerField(default=0)
    # dispatch_started_at = models.DateTimeField(null=True)
    # dispatch_ended_at = models.DateTimeField(null=True)

    inbox_hash = models.CharField(max_length=255, null=True)
    outbox_hash = models.CharField(max_length=255, null=True)
    process_proof = models.TextField(null=True)
    status = models.CharField(
        max_length=255, choices=to_choices(spec.EndpointStatus))

    def log_consensus(self, consensus_id):
        self.consensus_logs.create(
            consensus_id=consensus_id,
            status=self.status,
            timestamp=get_now())

    def get_last_consensus_id(self):
        try:
            return self.consensus_logs.all().order_by("-id")[0].consensus_id
        except IndexError:
            return None


class EndpointLink(models.Model):
    endpoint = models.ForeignKey(Endpoint, related_name="links")
    to_box = models.CharField(max_length=255, choices=to_choices(spec.Box))
    from_box = models.CharField(max_length=255, choices=to_choices(spec.Box))
    from_endpoint_id = models.CharField(max_length=255)


class EndpointConsensusLog(models.Model):
    endpoint = models.ForeignKey(Endpoint, related_name="consensus_logs")
    consensus_id = models.CharField(max_length=255)
    timestamp = models.DateTimeField()
    status = models.CharField(
        max_length=255, choices=to_choices(spec.EndpointStatus))

    class Meta:
        index_together = ["endpoint", "id"]


class Message(models.Model):
    serial = models.IntegerField(null=True)
    sender = models.CharField(max_length=255)  # some peer
    recipient = models.CharField(max_length=255)  # some peer
    text = models.TextField()
    message_hash = models.CharField(max_length=255)
    endpoint_id = models.CharField(max_length=255)
    box = models.CharField(
        max_length=255, choices=to_choices(spec.Box), db_index=True)

    class Meta:
        unique_together = ["endpoint_id", "box", "message_hash"]
        index_together = ["endpoint_id", "box", "id"]
