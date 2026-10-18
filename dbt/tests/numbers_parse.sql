-- A non-blank CMS number that fails to parse is a format change upstream, not a missing value.
select record:Tot_Clms::string as raw_claims, record:Tot_Drug_Cst::string as raw_cost
from {{ source('raw', 'partd_prescriber_drug') }}
where (nullif(trim(record:Tot_Clms::string), '') is not null and try_to_number(trim(record:Tot_Clms::string)) is null)
   or (nullif(trim(record:Tot_Drug_Cst::string), '') is not null
       and try_to_decimal(trim(record:Tot_Drug_Cst::string), 38, 2) is null)
