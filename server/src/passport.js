const passport = require('passport');
const GoogleStrategy = require('passport-google-oauth20').Strategy;
const { PrismaClient } = require('@prisma/client');

const prisma = new PrismaClient();

passport.serializeUser((user, done) => {
    done(null, user.id);
});

passport.deserializeUser(async (id, done) => {
    try {
        const user = await prisma.user.findUnique({ where: { id } });
        done(null, user);
    } catch (err) {
        done(err, null);
    }
});

passport.use(new GoogleStrategy({
    clientID: process.env.GOOGLE_CLIENT_ID,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    callbackURL: '/auth/google/callback'
}, async (accessToken, refreshToken, profile, done) => {
    try {
        // Build user object from profile
        const email = profile.emails[0].value;
        const googleId = profile.id;
        const name = profile.displayName;
        const avatar = profile.photos && profile.photos[0] ? profile.photos[0].value : null;

        // Upsert user
        const user = await prisma.user.upsert({
            where: { googleId },
            update: {
                name,
                avatar
            },
            create: {
                googleId,
                email,
                name,
                avatar
            }
        });

        return done(null, user);
    } catch (err) {
        return done(err, null);
    }
}));
