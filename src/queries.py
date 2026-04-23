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
    sa.region_c AS resellercustomer_region,
    sa.industry AS resellercustomer_industry,
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
LEFT JOIN cleansed.salesforce.salesforce_account_bcv sa ON a.crm_id = sa.id
WHERE
    s.status = 'Active'
    AND (s.subscription_kind_c = 'Primary' OR s.subscription_kind_c IS NULL OR s.subscription_kind_c = '')
    AND rpc.effective_start_date <= CURRENT_DATE()
    AND rpc.effective_end_date > CURRENT_DATE()
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
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


def partner_details_query(names):
    name_filter = _like_clause("a.name", names)
    return f"""
SELECT
    a.name AS partner_name,
    a.type AS account_type,
    a.channel_category_c AS channel_category,
    a.partner_level_c AS partner_level,
    a.signed_agreement_c AS signed_agreement,
    a.agreement_date_c AS agreement_date,
    a.partner_type_c AS partner_type,
    a.partner_status_c AS partner_status,
    a.partner_serviced_region_c AS serviced_region,
    u.name AS account_owner
FROM cleansed.salesforce.salesforce_account_bcv a
LEFT JOIN cleansed.salesforce.salesforce_user_bcv u ON a.owner_id = u.id
WHERE {name_filter}
  AND a.record_type_id = '01280000000Hi8UAAS'
  AND a.partner_status_c = 'Authorized'
ORDER BY a.name
"""


def partner_open_pipeline_query(names):
    name_filter = _like_clause("part.partner", names)
    return f"""
WITH open_pipeline AS (
  SELECT
      gtm.crm_opportunity_id,
      gtm.crm_account_name,
      gtm.stage_name,
      gtm.closedate,
      gtm.product,
      gtm.product_arr_usd,
      gtm.product_booking_arr_usd,
      gtm.industry,
      part.deal_type,
      part.partner,
      part.partner_deal_source,
      CASE
        WHEN part.partner IS NOT NULL AND part.partner_deal_source = 'Partner Sourced' THEN 'Partner Sourced'
        WHEN part.partner IS NOT NULL AND part.partner_deal_source = 'Zendesk Sourced' THEN 'Partner Influenced'
        ELSE NULL
      END AS sourced_influenced
  FROM FUNCTIONAL.GTM_SALES_OPS.GTMSI_CONSOLIDATED_PIPELINE_BOOKINGS gtm
  LEFT JOIN FUNCTIONAL.GTM_SALES_OPS.PARTNER_OPP_TABLE_ALL part
    ON part.id = gtm.crm_opportunity_id
  WHERE gtm.date_label = 'today'
    AND gtm.stage_2_plus_date_c IS NOT NULL
    AND gtm.opportunity_is_commissionable = TRUE
    AND gtm.stage_name IN ('02 - Confirm Need', '03 - Establish Value', '04 - Demonstrate Value', '05 - Secure Commitment', '06 - Contracting')
    AND {name_filter}
)

SELECT
    crm_opportunity_id,
    crm_account_name,
    stage_name,
    closedate,
    product,
    product_arr_usd,
    product_booking_arr_usd,
    industry,
    deal_type,
    partner,
    partner_deal_source,
    sourced_influenced
FROM open_pipeline
WHERE partner IS NOT NULL
  AND product_arr_usd > 0
ORDER BY product_arr_usd DESC
"""


def partner_certifications_query(names):
    name_filter = _like_clause("a.name", names)
    return f"""
SELECT
    pp.NAME AS PATH_PROGRESS_NAME,
    pp.STATUS_C,
    pp.COURSES_COMPLETE_C,
    pp.SKILLJAR_COMPLETED_AT_C,
    p.SKILLJAR_TITLE_C AS PATH_NAME,
    m.COURSE_GROUP,
    c.NAME AS CONTACT_NAME,
    c.EMAIL AS CONTACT_EMAIL,
    a.NAME AS ACCOUNT_NAME,
    a.PARTNER_LEVEL_C,
    a.PARTNER_STATUS_C
FROM CLEANSED.SALESFORCE.SALESFORCE_SKILLJAR_PATH_PROGRESS_C_BCV pp
LEFT JOIN CLEANSED.SALESFORCE.SALESFORCE_CONTACT_BCV c
    ON pp.SKILLJAR_CONTACT_C = c.ID
LEFT JOIN CLEANSED.SALESFORCE.SALESFORCE_ACCOUNT_BCV a
    ON c.ACCOUNT_ID = a.ID
LEFT JOIN CLEANSED.SALESFORCE.SALESFORCE_SKILLJAR_PATH_C_BCV p
    ON pp.SKILLJAR_PATH_C = p.ID
LEFT JOIN FUNCTIONAL.GTM_SALES_OPS.DIM_PARTNER_COURSE_MAPPING m
    ON p.SKILLJAR_TITLE_C = m.PUBLISHED_PATH_TILE
WHERE {name_filter}
  AND a.record_type_id = '01280000000Hi8UAAS'
ORDER BY m.COURSE_GROUP, pp.STATUS_C, a.NAME
"""


def sourced_pipeline_query(names, fiscal_quarters):
    name_filter = _like_clause("a.name", names)
    fq_list = ", ".join(f"'{fq}'" for fq in fiscal_quarters)
    return f"""
WITH PRODUCT_ARR AS (
    SELECT
        G.CRM_OPPORTUNITY_ID,
        SUM(CASE WHEN G.PRODUCT IN ('AR','Copilot','AI_Expert','Ultimate','WEM','QA')
            THEN G.PRODUCT_ARR_USD ELSE 0 END) AS NEW_AI_BOOKING_ARR_USD,
        SUM(CASE WHEN G.PRODUCT = 'ES'
            THEN G.PRODUCT_ARR_USD ELSE 0 END) AS ES_BOOKING_ARR_USD,
        SUM(CASE WHEN G.PRODUCT = 'Contact_Center'
            THEN G.PRODUCT_ARR_USD ELSE 0 END) AS CCaaS_BOOKING_ARR_USD
    FROM FUNCTIONAL.GTM_SALES_OPS.GTMSI_CONSOLIDATED_PIPELINE_BOOKINGS AS G
    WHERE G.DATE_LABEL = 'today'
    GROUP BY ALL
    HAVING (NEW_AI_BOOKING_ARR_USD > 0 OR ES_BOOKING_ARR_USD > 0 OR CCaaS_BOOKING_ARR_USD > 0)
),
partner_ids AS (
    SELECT DISTINCT a.id
    FROM cleansed.salesforce.salesforce_account_bcv a
    WHERE {name_filter}
      AND a.record_type_id = '01280000000Hi8UAAS'
)

SELECT
    FACT_OPP.CRM_OPPORTUNITY_ID,
    DIM_OPP.OPPORTUNITY_NAME,
    DIM_OPP.OPPORTUNITY_STAGE_NAME,
    DIM_ACC.CRM_ACCOUNT_NAME,
    D.FISCAL_YEAR_QUARTER,
    DIM_OPP.OPPORTUNITY_TYPE,
    FACT_OPP.OPPORTUNITY_BOOKING_ARR_USD,
    DIM_ACC.PRO_FORMA_REGION,
    DIM_ACC.PRO_FORMA_MARKET_SEGMENT,
    P.NEW_AI_BOOKING_ARR_USD,
    P.ES_BOOKING_ARR_USD,
    P.CCaaS_BOOKING_ARR_USD,
    FORMULA.CTC_PARTNER_NAME_C,
    DIM_OPP_2.PARTNER_DEAL_SOURCE_C,
    part.partner_type
FROM FOUNDATIONAL.CUSTOMER.FACT_CRM_OPPORTUNITIES_DAILY_SNAPSHOT AS FACT_OPP
LEFT JOIN FOUNDATIONAL.CUSTOMER.DIM_CRM_OPPORTUNITIES_DAILY_SNAPSHOT AS DIM_OPP
    ON FACT_OPP.CRM_OPPORTUNITY_SKEY = DIM_OPP.CRM_OPPORTUNITY_SKEY
LEFT JOIN FOUNDATIONAL.CUSTOMER.DIM_CRM_ACCOUNTS_DAILY_SNAPSHOT AS DIM_ACC
    ON FACT_OPP.CRM_ACCOUNT_SKEY = DIM_ACC.CRM_ACCOUNT_SKEY
LEFT JOIN (
    SELECT DISTINCT CRM_OPPORTUNITY_ID, GTM_TEAM, OPPORTUNITY_SOURCE_TYPE
    FROM FUNCTIONAL.MARKETING_ANALYTICS.SFDC_OPPORTUNITIES_TOUCHPOINT
) AS MKT_OPS
    ON DIM_OPP.CRM_OPPORTUNITY_ID = MKT_OPS.CRM_OPPORTUNITY_ID
LEFT JOIN FOUNDATIONAL.CUSTOMER.DIM_CRM_USERS_DAILY_SNAPSHOT_BCV AS USER_INFO
    ON DIM_ACC.CRM_OWNER_ID = USER_INFO.CRM_USER_ID
LEFT JOIN PRODUCT_ARR AS P
    ON FACT_OPP.CRM_OPPORTUNITY_ID = P.CRM_OPPORTUNITY_ID
LEFT JOIN CLEANSED.SALESFORCE.SALESFORCE_OPPORTUNITY_BCV AS DIM_OPP_2
    ON FACT_OPP.CRM_OPPORTUNITY_ID = DIM_OPP_2.ID
LEFT JOIN FUNCTIONAL.GTM_SALES_OPS.PARTNER_OPP_TABLE_ALL part
    ON part.id = FACT_OPP.CRM_OPPORTUNITY_ID
LEFT JOIN CLEANSED.SALESFORCE.SALESFORCE_OPPORTUNITY_FORMULA_BCV AS FORMULA
    ON FACT_OPP.CRM_OPPORTUNITY_ID = FORMULA.ID
LEFT JOIN FOUNDATIONAL.FINANCE.DIM_DATE AS D
    ON DIM_OPP.OPPORTUNITY_STAGE_2_PLUS_DATE = D.THE_DATE
WHERE
    D.FISCAL_YEAR_QUARTER IN ({fq_list})
    AND FACT_OPP.SOURCE_SNAPSHOT_DATE = (
        SELECT MAX(SOURCE_SNAPSHOT_DATE)
        FROM FOUNDATIONAL.CUSTOMER.FACT_CRM_OPPORTUNITIES_DAILY_SNAPSHOT
    )
    AND DIM_OPP.OPPORTUNITY_STAGE_2_PLUS_DATE IS NOT NULL
    AND DIM_OPP.OPPORTUNITY_STAGE_NAME NOT IN ('00 - Prospect & Plan', '01 - Qualify Need', '01 - Qualifying')
    AND FACT_OPP.OPPORTUNITY_BOOKING_ARR_USD > 0
    AND DIM_OPP.OPPORTUNITY_IS_COMMISSIONABLE = 1
    AND DIM_OPP.OPPORTUNITY_TYPE IN ('New Business', 'Expansion')
    AND MKT_OPS.GTM_TEAM = 'Partner'
    AND (DIM_OPP_2.DEAL_LOST_REASON_MULTI_C IS NULL OR DIM_OPP_2.DEAL_LOST_REASON_MULTI_C NOT LIKE '%Duplicate%')
    AND DIM_OPP_2.IMPARTNER_PRM_PARTNER_ACCOUNT_C IN (SELECT id FROM partner_ids)
ORDER BY FACT_OPP.OPPORTUNITY_BOOKING_ARR_USD DESC
"""
