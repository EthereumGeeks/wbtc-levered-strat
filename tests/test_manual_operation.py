from brownie import *
import pytest

"""
Tests for Manual Delveraging, harvesting, etc...
"""


def test_manual_manualDivestFromAAVE(
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
):
    ## Check current leverage ratio
    prev_debt = borrowed.balanceOf(levered_strat)
    assert prev_debt > 0

    ## Deleverage manually
    levered_strat.manualDivestFromAAVE({"from": gov})

    ## Assert that there's no debt
    assert borrowed.balanceOf(levered_strat) == 0


def test_manual_manualLeverUp(
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
    gov,
    levered_strat,
):
    prev_debt = borrowed.balanceOf(levered_strat)
    assert prev_debt > 0

    ## Deleverage manually
    levered_strat.manualDivestFromAAVE({"from": gov})

    ## Assert that there's no debt
    assert borrowed.balanceOf(levered_strat) == 0

    ## After deleverage, you have to harvest to re-deposit
    levered_strat.harvest()

    prev_lev_deb = borrowed.balanceOf(levered_strat)
    prev_lev_dep = lpComponent.balanceOf(levered_strat)

    prev_assets = levered_strat.estimatedTotalAssets()

    chain.sleep(1)  ## Seems like ganache stops noticing changes without it
    ## We're at 0, let's lever up
    levered_strat.manualLeverUp({"from": gov})

    ## No changes in totalAssets
    assert (
        pytest.approx(levered_strat.estimatedTotalAssets(), rel=RELATIVE_APPROX)
        == prev_assets
    )

    ## But debt and aToken are increased
    assert borrowed.balanceOf(levered_strat) > prev_lev_deb
    assert lpComponent.balanceOf(levered_strat) > prev_lev_dep


def test_manual_manualWithdrawStepFromAAVE(
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
    gov,
    levered_strat,
):
    prev_deposited = lpComponent.balanceOf(levered_strat)
    prev_debt = borrowed.balanceOf(levered_strat)
    prev_assets = levered_strat.estimatedTotalAssets()
    assert prev_debt > 0

    max_repay = levered_strat.canRepay()

    ## Delever by max_repay (just like the strat would)
    levered_strat.manualWithdrawStepFromAAVE(max_repay, {"from": gov})

    ## No changes in totalAssets
    assert (
        pytest.approx(levered_strat.estimatedTotalAssets(), rel=RELATIVE_APPROX)
        == prev_assets
    )

    ## We have less debt
    assert borrowed.balanceOf(levered_strat) < prev_debt
    assert lpComponent.balanceOf(levered_strat) < prev_deposited


def test_manual_RepayFromManager(
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
    gov,
    levered_strat,
):
    prev_deposited = lpComponent.balanceOf(levered_strat)
    prev_debt = borrowed.balanceOf(levered_strat)
    prev_assets = levered_strat.estimatedTotalAssets()
    assert prev_debt > 0

    amount = 100000

    token.approve(
        levered_strat, amount, {"from": gov}
    )  ## Gov has a little bit of performance fees
    levered_strat.manualRepayFromManager(amount, {"from": gov})

    ## Assets have increased
    assert levered_strat.estimatedTotalAssets() > prev_assets

    ## We have the same amount invested ## it accrues interest hence we approx
    assert (
        pytest.approx(lpComponent.balanceOf(levered_strat), rel=RELATIVE_APPROX)
        == prev_deposited
    )

    ## We reduced Debt
    assert borrowed.balanceOf(levered_strat) < prev_debt


def test_manual_manualClaimRewards(reward, gov, levered_strat):
    prev_rewards = reward.balanceOf(levered_strat)

    levered_strat.manualClaimRewards({"from": gov})

    assert reward.balanceOf(levered_strat) > prev_rewards


def test_manual_manualCooldownRewards(
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
    gov,
    levered_strat,
):
    prev_rewards = reward.balanceOf(levered_strat)

    levered_strat.manualClaimRewards({"from": gov})

    assert reward.balanceOf(levered_strat) > prev_rewards

    levered_strat.manualCooldownRewards({"from": gov})


def test_manual_manualRedeemRewards(
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
    gov,
    aave,
    levered_strat,
):
    prev_rewards = reward.balanceOf(levered_strat)
    prev_aave = aave.balanceOf(levered_strat)

    levered_strat.manualClaimRewards({"from": gov})

    assert reward.balanceOf(levered_strat) > prev_rewards

    levered_strat.manualCooldownRewards({"from": gov})

    ## Wait 11 days
    chain.sleep(3600 * 24 * 11)  # 10 days to unlock, extra time for caution

    levered_strat.manualRedeemRewards({"from": gov})

    assert aave.balanceOf(levered_strat) > prev_aave


def test_manual_manualSwapFromStkAAVEToAAVE(
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
    gov,
    aave,
    levered_strat,
):
    prev_rewards = reward.balanceOf(levered_strat)
    prev_aave = aave.balanceOf(levered_strat)

    levered_strat.manualClaimRewards({"from": gov})

    assert reward.balanceOf(levered_strat) > prev_rewards

    levered_strat.manualSwapFromStkAAVEToAAVE(
        reward.balanceOf(levered_strat), 10 ** 18 * 0.95, {"from": gov}
    )  ## 5% slippage

    assert aave.balanceOf(levered_strat) > prev_aave


def test_manual_manualSwapFromAAVEToWant(
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
    gov,
    aave,
    levered_strat,
):
    prev_rewards = reward.balanceOf(levered_strat)
    prev_aave = aave.balanceOf(levered_strat)
    prev_assets = levered_strat.estimatedTotalAssets()

    levered_strat.manualClaimRewards({"from": gov})

    assert reward.balanceOf(levered_strat) > prev_rewards

    levered_strat.manualSwapFromStkAAVEToAAVE(
        reward.balanceOf(levered_strat), 10 ** 18 * 0.95, {"from": gov}
    )  ## 5% slippage

    new_aave_bal = aave.balanceOf(levered_strat)
    assert new_aave_bal > prev_aave

    ## From google 1 AAVE = 0.00789100 BTC
    levered_strat.manualSwapFromAAVEToWant(
        new_aave_bal, 0.00589100 * 10 ** 8, {"from": gov}
    )  ## 1 to 1, massive discount but better than 0

    ## We earned some, in both ways of calculating
    assert (
        token.balanceOf(levered_strat)
        + levered_strat.deposited()
        - levered_strat.borrowed()
        > prev_assets
    )
    assert levered_strat.estimatedTotalAssets() > prev_assets
