docker run --env-file .env -v `pwd`/vpn_configs:/app/vpn_configs --cap-add=NET_ADMIN --rm -it --name mt-rose-lift-checker mt-rose-lift-checker
