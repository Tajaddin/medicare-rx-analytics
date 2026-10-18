-- Products a broad name pattern puts in the wrong class, pinned to the class reviewed for them on 2026-10-18
-- against every product in the 2022-2024 Florida data and the national spending file. A product that is not in
-- the loaded data is skipped, so the test also runs on the CI sample.
with expected as (
    select * from (values
        ('apokyn', 'apomorphine hcl', 'other'),
        ('relistor', 'methylnaltrexone bromide', 'other'),
        ('contrave', 'naltrexone hcl/bupropion hcl', 'other'),
        ('vivitrol', 'naltrexone microspheres', 'other'),
        ('butrans', 'buprenorphine', 'opioid_analgesic'),
        ('buprenorphine', 'buprenorphine', 'opioid_analgesic'),
        ('belbuca', 'buprenorphine hcl', 'opioid_analgesic'),
        ('sublocade', 'buprenorphine', 'opioid_use_disorder'),
        ('brixadi', 'buprenorphine', 'opioid_use_disorder'),
        ('buprenorphine hcl', 'buprenorphine hcl', 'opioid_use_disorder'),
        ('suboxone', 'buprenorphine hcl/naloxone hcl', 'opioid_use_disorder'),
        ('acetaminophen-codeine', 'acetaminophen with codeine', 'opioid_analgesic'),
        ('promethazine-codeine', 'promethazine hcl/codeine', 'opioid_antitussive'),
        ('codeine-guaifenesin', 'codeine phosphate/guaifenesin', 'opioid_antitussive'),
        ('hydromet', 'hydrocodone bit/homatrop me-br', 'opioid_antitussive'),
        ('soliqua 100-33', 'insulin glargine/lixisenatide', 'glp1_receptor_agonist'),
        ('xultophy 100-3.6', 'insulin degludec/liraglutide', 'glp1_receptor_agonist'),
        ('v-go 20', 'sub-q insulin device, 20 unit', 'diabetes_supply'),
        ('bd insulin syringe', 'syringe and needle,insulin,1ml', 'diabetes_supply'),
        ('omnipod dash pods (gen 4)', 'insulin pump cart,cont inf,bt', 'diabetes_supply'),
        ('lantus', 'insulin glargine,hum.rec.anlog', 'insulin'),
        ('ozempic', 'semaglutide', 'glp1_receptor_agonist'),
        ('mounjaro', 'tirzepatide', 'glp1_receptor_agonist')
    ) as t (brand, generic, drug_class)
)

select e.brand, e.generic, e.drug_class as expected_class, c.drug_class as actual_class
from expected as e
inner join {{ ref('int_drug_class') }} as c
    on lower(c.brand_name) = e.brand and lower(c.generic_name) = e.generic
where c.drug_class <> e.drug_class
