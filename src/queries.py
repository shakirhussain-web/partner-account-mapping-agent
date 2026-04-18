def _like_clause(column, names):
    conditions = []
    for name in names:
        escaped = name.replace("'", "''")
        conditions.append(f"LOWER({column}) LIKE LOWER('%{escaped}%')")
    return "(" + " OR ".join(conditions) + ")"


def reseller_subscriptions_query(names):
    name_filter = _like_clause("a.name", names)
    return f"""
WITH reseller AS (
    SELECT
        a.id AS zuora_account_id,
        a.account_number AS zuora_account_number,
        a.name AS zuora_account_name,
        a.crm_id AS sfdc_id,
        a.account_type_c AS account_type
    FROM cleansed.zuora.zuora_accounts_bcv a
    WHERE a.name NOT LIKE '%z4n%'
      AND a.account_type_c = 'Reseller'
      AND {name_filter}
    GROUP BY 1, 2, 3, 4, 5
)

SELECT
    r.zuora_account_id,
    r.zuora_account_number,
    r.zuora_account_name,
    r.sfdc_id,
    r.account_type,
    a.id AS resellercustomer_account_id,
    a.account_number AS resellercustomer_accountnumber,
    a.name AS resellercustomer_accountname,
    TRY_CAST(a.zendesk_account_id_c AS INT) AS resellercustomer_zendesk_id,
    z.subdomain_c AS resellercustomer_subdomain,
    a.crm_id AS resellercustomer_sfdc_id,
    a.status AS resellercustomer_status,
    a.mrr * 12 AS resellercustomer_arr,
    a.currency AS resellercustomer_currency,
    s.id AS resellercustomer_sub_id,
    s.name AS resellercustomer_sub_number,
    s.term_end_date AS resellercustomer_sub_renewal_date,
    s.status AS resellercustomer_sub_status,
    LISTAGG(DISTINCT rpc.name, ', ') AS product_names,
    SUM(rpc.quantity) AS total_quantity,
    MAX(rpc.billing_period) AS billing_period
FROM reseller r
LEFT JOIN cleansed.zuora.zuora_accounts_bcv a ON r.zuora_account_id = a.parent_account_id
LEFT JOIN cleansed.zuora.zuora_subscriptions_bcv s ON a.id = s.account_id
LEFT JOIN cleansed.zuora.zuora_rate_plan_charges_bcv rpc ON s.id = rpc.subscription_id
LEFT JOIN cleansed.zuora.zuora_products_bcv p ON rpc.product_id = p.id
LEFT JOIN cleansed.salesforce.salesforce_zuora_customer_account_c_bcv z
  ON TRY_CAST(a.zendesk_account_id_c AS INT) = TRY_CAST(z.zendesk_account_id_c AS INT)
WHERE
    s.status = 'Active'
    AND (s.subscription_kind_c = 'Primary' OR s.subscription_kind_c IS NULL OR s.subscription_kind_c = '')
    AND rpc.effective_start_date <= CURRENT_DATE()
    AND rpc.effective_end_date > CURRENT_DATE()
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18
ORDER BY r.zuora_account_name ASC, a.name ASC
"""


def partner_bookings_query(names):
    name_filter = _like_clause("partner", names)
    return f"""
WITH partner_rawdata AS (
  SELECT
      DISTINCT gtm.* EXCLUDE(partner_type),
      CASE
        WHEN gtm.opportunity_is_commissionable = TRUE
         AND gtm.type NOT IN ('New Business', 'Expansion') THEN 'Expansion'
        ELSE gtm.type
      END AS type_gtm,
      CASE
        WHEN top.top_3000_flag = TRUE THEN 'Top 3k'
        ELSE 'Not Top 3k'
      END AS top_3000_flag,
      part.deal_type,
      part.partner,
      part.pse,
      part.partner_owner,
      part.partner_tier,
      part.partner_type,
      part.partner_deal_source,
      sfdc_bcv.PSE_DEAL_FORECAST_C,
      sfdc_bcv.referring_partner_c,
      CASE
        WHEN part.partner IS NOT NULL AND part.partner_deal_source = 'Partner Sourced' THEN 'Partner Sourced'
        WHEN part.partner IS NOT NULL AND part.partner_deal_source = 'Zendesk Sourced' THEN 'Partner Influenced'
        ELSE NULL
      END AS sourced_influenced
  FROM FUNCTIONAL.GTM_SALES_OPS.GTMSI_CONSOLIDATED_PIPELINE_BOOKINGS gtm
  LEFT JOIN FUNCTIONAL.GTM_SALES_OPS.PARTNER_OPP_TABLE_ALL part
    ON part.id = gtm.crm_opportunity_id
  LEFT JOIN CLEANSED.SALESFORCE.SALESFORCE_OPPORTUNITY_BCV sfdc_bcv
    ON sfdc_bcv.id = gtm.crm_opportunity_id
  LEFT JOIN PRESENTATION.PRODUCT_ANALYTICS.AI_COMBINED_CRM_DAILY_SNAPSHOT top
    ON gtm.crm_account_id = top.crm_account_id
   AND top.source_snapshot_date = (
        SELECT MAX(source_snapshot_date)
        FROM PRESENTATION.PRODUCT_ANALYTICS.AI_COMBINED_CRM_DAILY_SNAPSHOT
      )
  WHERE gtm.date_label = 'today'
    AND gtm.stage_2_plus_date_c IS NOT NULL
    AND gtm.closedate >= TO_DATE('2025-02-01')
    AND gtm.opportunity_is_commissionable = TRUE
    AND gtm.stage_name IN ('08 - Closed', '07 - Signed', 'Failed Finance Audit')
    AND sourced_influenced IN ('Partner Sourced', 'Partner Influenced')
)

SELECT DISTINCT
    close_year_quarter,
    stage_name,
    region,
    sourced_influenced,
    product,
    product_arr_usd AS pipeline,
    product_booking_arr_usd AS bookings,
    deal_type,
    type_gtm,
    crm_opportunity_id,
    closedate,
    stage_2_plus_date_c,
    crm_account_id,
    crm_account_name,
    partner,
    pse,
    partner_owner,
    partner_tier,
    partner_type,
    industry,
    top_3000_flag,
    pro_forma_market_segment,
    pro_forma_subregion,
    TERRITORY_COUNTRY__C_OPPT,
    PSE_DEAL_FORECAST_C,
    gtm_team,
    referring_partner_c AS Partner_ID
FROM partner_rawdata
WHERE partner IS NOT NULL
  AND product_booking_arr_usd > 0
  AND {name_filter}
"""
