cd "/Users/krrishsethiya/Documents/DE Projects/DE Project/NYC Lakehouse/scripts/dbt"
sed -i '' 's/unique_key='"'"'arrest_id'"'"'/unique_key='"'"'arrest_id'"'"',\n        location='"'"'s3:\/\/nyc-lakehouse-store\/silver\/staging\/stg_nypd_arrests'"'"'/g' models/staging/stg_nypd_arrests.sql
dbt compile --full-refresh -s stg_nypd_arrests
cat target/run/nyc_lakehouse_dbt/models/staging/stg_nypd_arrests.sql | grep -i location
git checkout models/staging/stg_nypd_arrests.sql
