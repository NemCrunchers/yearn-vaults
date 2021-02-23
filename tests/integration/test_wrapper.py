import pytest

from collections import namedtuple
from semantic_version import Version

from brownie import yToken, AffiliateToken, Vault
from brownie.test import strategy


class Migration:
    st_ratio = strategy("decimal", min_value="0.1", max_value="0.9")
    st_index = strategy("uint256")

    def __init__(
        self,
        registry,
        token,
        create_vault,
        wrapper,
        user,
        gov,
        initial_vault,
        balance_check_fn,
    ):
        self.registry = registry
        self.token = token
        self.create_vault = lambda s, t, v: create_vault(token=t, version=v)
        self.wrapper = wrapper
        self.user = user
        self.gov = gov
        self._initial_vault = initial_vault
        self.balance_check_fn = balance_check_fn
        self.returns_generated = 0

    def setup(self):
        self.vaults = [self._initial_vault]

    def rule_new_release(self):
        api_version = str(Version(self.registry.latestRelease()).next_major())
        vault = self.create_vault(self.token, api_version)
        print(f"  Registry.newRelease({vault})")
        self.registry.newRelease(vault, {"from": self.gov})
        if self.wrapper._name == "yToken":
            vault.approve(self.wrapper, 2 ** 256 - 1, {"from": self.user})
        self.vaults.append(vault)

    def rule_deposit(self, ratio="st_ratio"):
        amount = int(ratio * self.wrapper.balanceOf(self.user))
        if amount > 0:
            print(f"  Wrapper.deposit({amount})")
            self.wrapper.deposit(amount, {"from": self.user})

        else:
            print("  Wrapper.deposit: Nothing to deposit...")

    def rule_harvest(self, index="st_index"):
        # Give some profit to one of the Vaults we are invested in
        vaults_in_use = [v for v in self.vaults if v.totalSupply() > 0]
        if len(vaults_in_use) > 0:
            vault = vaults_in_use[index % len(vaults_in_use)]
            print(f"  {vault}.harvest()")
            amount = int(1e17)
            self.token.transfer(vault, amount, {"from": self.user})
            self.returns_generated += amount

        else:
            print("  vaults.harvest: No Vaults in use...")

    def rule_migrate(self):
        print("  Wrapper.migrate()")
        self.wrapper.migrate({"from": self.gov})

    def rule_withdraw(self, ratio="st_ratio"):
        amount = int(ratio * self.wrapper.balanceOf(self.user))
        if amount > 0:
            print(f"  Wrapper.withdraw({amount})")
            self.wrapper.withdraw(amount, {"from": self.user})

        else:
            print("  Wrapper.withdraw: Nothing to withdraw...")

    def invariant_balances(self):
        self.balance_check_fn()


@pytest.mark.parametrize("Wrapper", [yToken, AffiliateToken])
def test_migration_wrapper(
    state_machine, token, create_vault, whale, gov, registry, Wrapper
):
    starting_balance = token.balanceOf(whale)
    assert starting_balance > 0

    if Wrapper._name == "yToken":
        wrapper = gov.deploy(Wrapper, token)

        def balance_check_fn(self):
            assert (
                0
                <= starting_balance
                - self.token.balanceOf(self.user)
                - sum(
                    v.balanceOf(self.user) * v.pricePerShare() // 10 ** v.decimals()
                    for v in self.vaults
                )
                < 1000  # up to 1e3 difference in computing this number
            )

    else:
        wrapper = gov.deploy(Wrapper, token, "Test Affiliate Token", "afToken")

        def balance_check_fn(self):
            assert (
                0
                <= starting_balance
                - self.token.balanceOf(self.user)
                - (
                    self.wrapper.balanceOf(self.user)
                    * self.wrapper.pricePerShare()
                    // 10 ** self.wrapper.decimals()
                )
                < 1000  # up to 1e3 difference in computing this number
            )

    token.approve(wrapper, 2 ** 256 - 1, {"from": whale})

    # NOTE: Need to seed registry with at least one vault to function
    vault = create_vault(token=token, version="1.0.0")
    if wrapper._name == "yToken":
        vault.approve(wrapper, 2 ** 256 - 1, {"from": whale})
    registry.newRelease(vault, {"from": gov})

    # NOTE: Start with something deposited
    wrapper.deposit(starting_balance // 10, {"from": whale})
    # HACK: Get this function working correctly
    Caller = namedtuple("Caller", ["token", "vaults", "wrapper", "user"])
    caller = Caller(token, [vault], wrapper, whale)
    balance_check_fn(caller)
    del caller, Caller

    state_machine(
        Migration,
        registry,
        token,
        create_vault,
        wrapper,
        whale,
        gov,
        vault,
        balance_check_fn,
    )
