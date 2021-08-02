from brownie import *
import pytest

"""
Have the strat get liquidated, see what happens
"""


@pytest.fixture
def lending_pool(levered_strat):
    yield Contract.from_explorer(levered_strat.LENDING_POOL())


# @pytest.fixture
# def lpCore(levered_strat):
#   address_provider = Contract.from_explorer(levered_strat.ADDRESS_PROVIDER())
#   lpCore = Contract.from_explorer(address_provider.getLendingPoolCore())
#   yield lpCore


def get_health(lending_pool, strategy):
    (
        totalCollateralETH,
        totalDebtETH,
        availableBorrowsETH,
        currentLiquidationThreshold,
        ltv,
        healthFactor,
    ) = lending_pool.getUserAccountData(strategy)
    return healthFactor / (10 ** 18)


def get_maxLtv(lending_pool, strategy):
    (
        totalCollateralETH,
        totalDebtETH,
        availableBorrowsETH,
        currentLiquidationThreshold,
        ltv,
        healthFactor,
    ) = lending_pool.getUserAccountData(strategy)
    return currentLiquidationThreshold / 10000


def test_liquidation(
    levered_strat,
    gov,
    chain,
    accounts,
    token,
    vault,
    strategy,
    user,
    strategist,
    amount,
    RELATIVE_APPROX,
    lpComponent,
    borrowed,
    reward,
    incentivesController,
    lending_pool,
    aave,
):

    token.approve(lending_pool, 1000, {"from": gov})  ## Create reserve for Gov
    lending_pool.deposit(token, 1000, gov, 0, {"from": gov})

    ## Wait for 15 years so we loose a ton of money
    chain.sleep(3600 * 24 * 365 * 15)
    chain.mine(1)

    assert get_health(lending_pool, strategy) < 1

    total_debt = borrowed.balanceOf(strategy)
    total_deposits = lpComponent.balanceOf(strategy)

    max_debt = total_deposits * get_maxLtv(lending_pool, strategy)

    to_liquidate = total_debt - max_debt

    ## Get liquidated
    token.approve(lending_pool, to_liquidate, {"from": gov})
    lending_pool.liquidationCall(
        token, token, levered_strat, to_liquidate, False, {"from": gov}
    )
    chain.mine(1)

    ## Avoid random reverts - Empty rewards and swap manually
    levered_strat.setMin(
        levered_strat.minHealth(),
        0,
        0,
        levered_strat.minRebalanceAmount(),
        {"from": gov},
    )
    chain.mine(1)

    ## Call harvest
    levered_strat.setDoHealthCheck(
        False, {"from": gov}
    )  ## We waited 11 years, this will break health check
    levered_strat.harvest()

    harvest_event = history[-1].events["Harvested"]
    assert harvest_event["loss"] > 0
