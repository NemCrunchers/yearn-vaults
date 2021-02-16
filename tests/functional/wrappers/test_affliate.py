import brownie


def test_config(gov, token, vault, registry, affiliate_token):
    assert affiliate_token.token() == token
    assert affiliate_token.name() == "Affiliate " + token.symbol()
    assert affiliate_token.symbol() == "af" + token.symbol()
    assert affiliate_token.decimals() == vault.decimals() == token.decimals()

    # No vault added to the registry yet, so these methods should fail
    assert registry.nextDeployment(token) == 0

    with brownie.reverts():
        affiliate_token.bestVault()

    # This won't revert though, there's no Vaults yet
    assert affiliate_token.allVaults() == []

    # Now they work when we have a Vault
    registry.newRelease(vault, {"from": gov})
    assert affiliate_token.bestVault() == vault
    assert affiliate_token.allVaults() == [vault]


def test_setRegistry(rando, affiliate, affiliate_token):
    with brownie.reverts():
        affiliate_token.setRegistry(rando, {"from": rando})

    # Only affiliate can call this method
    affiliate_token.setRegistry(rando, {"from": affiliate})


def test_deposit(token, registry, vault, affiliate_token, gov, rando):
    registry.newRelease(vault, {"from": gov})
    token.transfer(rando, 10000, {"from": gov})
    assert affiliate_token.balanceOf(rando) == vault.balanceOf(rando) == 0

    # NOTE: Must approve affiliate_token to deposit
    token.approve(affiliate_token, 10000, {"from": rando})
    affiliate_token.deposit(10000, {"from": rando})
    assert affiliate_token.balanceOf(rando) == 10000
    assert vault.balanceOf(rando) == 0


def test_migrate(token, registry, create_vault, affiliate_token, gov, rando, affiliate):
    vault1 = create_vault(version="1.0.0", token=token)
    registry.newRelease(vault1, {"from": gov})
    token.transfer(rando, 10000, {"from": gov})
    token.approve(affiliate_token, 10000, {"from": rando})
    affiliate_token.deposit(10000, {"from": rando})
    assert affiliate_token.balanceOf(rando) == 10000
    assert vault1.balanceOf(affiliate_token) == 10000

    vault2 = create_vault(version="2.0.0", token=token)
    registry.newRelease(vault2, {"from": gov})

    with brownie.reverts():
        affiliate_token.migrate({"from": rando})

    # Only affiliate can call this method
    affiliate_token.migrate({"from": affiliate})
    assert affiliate_token.balanceOf(rando) == 10000
    assert vault1.balanceOf(affiliate_token) == 0
    assert vault2.balanceOf(affiliate_token) == 10000


def test_transfer(token, registry, vault, affiliate_token, gov, rando, affiliate):
    registry.newRelease(vault, {"from": gov})
    token.transfer(rando, 10000, {"from": gov})
    token.approve(affiliate_token, 10000, {"from": rando})
    affiliate_token.deposit(10000, {"from": rando})

    # NOTE: Just using `affiliate` as a random address
    affiliate_token.transfer(affiliate, 10000, {"from": rando})
    assert affiliate_token.balanceOf(rando) == 0
    assert affiliate_token.balanceOf(affiliate) == 10000
    assert token.balanceOf(rando) == token.balanceOf(affiliate) == 0


def test_withdraw(token, registry, vault, affiliate_token, gov, rando):
    registry.newRelease(vault, {"from": gov})
    token.transfer(rando, 10000, {"from": gov})
    token.approve(affiliate_token, 10000, {"from": rando})
    affiliate_token.deposit(10000, {"from": rando})

    # NOTE: Must approve affiliate_token to withdraw
    affiliate_token.withdraw(10000, {"from": rando})
    assert affiliate_token.balanceOf(rando) == 0
    assert token.balanceOf(rando) == 10000
