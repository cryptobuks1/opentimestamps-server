# Copyright (C) 2016 The OpenTimestamps developers
#
# This file is part of python-opentimestamps.
#
# It is subject to the license terms in the LICENSE file found in the top-level
# directory of this distribution.
#
# No part of python-opentimestamps including this file, may be copied,
# modified, propagated, or distributed except according to the terms contained
# in the LICENSE file.

from bitcoin.core import b2lx

from opentimestamps.core.timestamp import Timestamp,OpAppend, OpPrepend, OpVerify
from opentimestamps.timestamp import cat_sha256d
from opentimestamps.core.notary import BitcoinBlockHeaderAttestation

def __make_btc_block_merkle_tree(blk_txids):
    assert len(blk_txids) > 0

    digests = blk_txids
    while len(digests) > 1:
        # The famously broken Satoshi algorithm: if the # of digests at this
        # level is odd, double the last one.
        if len(digests) % 2:
            digests.append(digests[-1].msg)

        next_level = []
        for i in range(0,len(digests),2):
            next_level.append(cat_sha256d(digests[i], digests[i + 1]))

        digests = next_level

    return digests[0]


def make_timestamp_from_block(digest, block, blockheight):
    """Make a timestamp for a digest from a block

    Returns a timestamp for that digest on success, None on failure
    """
    # Find the transaction containing the root digest
    #
    # FIXME: we actually should find the _smallest_ transaction containing
    # digest to ward off trolls...
    commitment_tx = None
    prefix = None
    suffix = None
    for tx in block.vtx:
        serialized_tx = tx.serialize()

        try:
            i = serialized_tx.index(digest)
        except ValueError:
            continue

        # Found it!
        commitment_tx = tx
        prefix = serialized_tx[0:i]
        suffix = serialized_tx[i + len(digest):]

        break
    else:
        return None

    digest_timestamp = Timestamp(digest)

    # Add the commitment ops necessary to go from the digest to the txid op
    prefix_op = digest_timestamp.add_op(OpPrepend, prefix)
    txid_stamp = cat_sha256d(prefix_op.timestamp, suffix)

    assert commitment_tx.GetHash() == txid_stamp.msg

    # Create the txid list, with our commitment txid op in the appropriate
    # place
    block_txid_stamps = []
    for tx in block.vtx:
        if tx.GetHash() != txid_stamp.msg:
            block_txid_stamps.append(Timestamp(tx.GetHash()))
        else:
            block_txid_stamps.append(txid_stamp)

    # Build the merkle tree
    merkleroot_stamp = __make_btc_block_merkle_tree(block_txid_stamps)

    attestation = BitcoinBlockHeaderAttestation(blockheight)
    merkleroot_stamp.add_op(OpVerify, attestation)

    return digest_timestamp
