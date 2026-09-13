import discord
from discord import app_commands
from discord.ext import commands, tasks
import datetime
import os
import random
import asyncio
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True


class AqiraxBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # Almacén de sorteos activos: {message_id: Giveaway}
        self.giveaways = {}

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Comandos de barra sincronizados.")
        # Iniciar el loop que revisa sorteos finalizados
        self.check_giveaways.start()

    async def on_ready(self):
        print(f"🤖 Bot conectado como {self.user} (ID: {self.user.id})")

        await self.change_presence(
            status=discord.Status.dnd,
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="El Futuro Es Hoy."
            )
        )

        for guild in self.guilds:
            await self.setup_automod(guild)

        # Reanudar sorteos activos desde el canal (si el bot se reinició)
        await self.recover_giveaways()

    async def recover_giveaways(self):
        """Intenta recuperar sorteos activos desde los mensajes fijados."""
        for guild in self.giveaways.values():
            pass  # Reservado para persistencia futura con DB
        print(f"ℹ️ Sorteos en memoria: {len(self.giveaways)}")

    async def setup_automod(self, guild: discord.Guild):
        try:
            existing_rules = await guild.fetch_automod_rules()
            if any(rule.name == "Aqirax Link Blocker" for rule in existing_rules):
                return

            regex_patterns = [
                r"https?://(www\.)?discord\.gg/\S+",
                r"https?://(www\.)?discord\.com/\S+",
                r"https?://(www\.)?youtube\.com/\S+"
            ]

            await guild.create_automod_rule(
                name="Aqirax Link Blocker",
                event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(
                    type=discord.AutoModRuleTriggerType.keyword,
                    regex_patterns=regex_patterns
                ),
                actions=[
                    discord.AutoModRuleAction(
                        type=discord.AutoModRuleActionType.block_message,
                        custom_message="🚫 Enlace bloqueado por AutoMod. El Futuro Es Hoy, pero no esos links."
                    )
                ],
                enabled=True,
                reason="Bloqueo de enlaces no permitidos (Discord, YouTube)"
            )
            print(f"✅ Regla de AutoMod creada en: {guild.name}")
        except discord.Forbidden:
            print(f"⚠️ Faltan permisos de AutoMod en: {guild.name}")
        except Exception as e:
            print(f"❌ Error creando AutoMod en {guild.name}: {e}")

    # --- LOOP QUE REVISA SORTEOS TERMINADOS CADA 10 SEGUNDOS ---
    @tasks.loop(seconds=10)
    async def check_giveaways(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        finished = []
        for msg_id, giveaway in list(self.giveaways.items()):
            if now >= giveaway.end_time and not giveaway.finished:
                finished.append(msg_id)

        for msg_id in finished:
            await self.finish_giveaway(msg_id)

    @check_giveaways.before_loop
    async def before_check(self):
        await self.wait_until_ready()

    async def finish_giveaway(self, message_id: int):
        giveaway = self.giveaways.get(message_id)
        if not giveaway or giveaway.finished:
            return

        giveaway.finished = True

        try:
            channel = self.get_channel(giveaway.channel_id)
            if channel is None:
                channel = await self.fetch_channel(giveaway.channel_id)
            message = await channel.fetch_message(message_id)
        except Exception as e:
            print(f"❌ No se pudo obtener el mensaje del sorteo {message_id}: {e}")
            self.giveaways.pop(message_id, None)
            return

        # Elegir ganador
        participants = list(giveaway.participants)
        if not participants:
            # Sin participantes
            embed = message.embeds[0] if message.embeds else discord.Embed(title=giveaway.title)
            embed.color = discord.Color.red()
            embed.add_field(
                name="🎉 Resultado",
                value="❌ Nadie participó en el sorteo.",
                inline=False
            )
            embed.set_footer(text="Sorteo finalizado sin ganador")
            try:
                await message.edit(embed=embed, view=None)
            except Exception:
                pass
            self.giveaways.pop(message_id, None)
            return

        winner_id = random.choice(participants)
        try:
            winner = await self.fetch_user(winner_id)
            winner_mention = winner.mention
            winner_name = str(winner)
            winner_avatar = winner.display_avatar.url
        except Exception:
            winner_mention = f"<@{winner_id}>"
            winner_name = f"Usuario {winner_id}"
            winner_avatar = None

        embed = message.embeds[0] if message.embeds else discord.Embed(title=giveaway.title)
        embed.color = discord.Color.gold()
        embed.add_field(
            name="🎉 Ganador",
            value=f"🏆 {winner_mention}",
            inline=False
        )
        embed.set_footer(text=f"Sorteo finalizado • {len(participants)} participantes")

        try:
            await message.edit(embed=embed, view=None)
            await channel.send(
                f"🎊 ¡Felicidades {winner_mention}! Has ganado el sorteo **{giveaway.title}**. "
                f"Contacta con un administrador para reclamar tu premio."
            )
        except Exception as e:
            print(f"❌ Error editando mensaje del sorteo: {e}")

        self.giveaways.pop(message_id, None)
        print(f"🎉 Sorteo finalizado: {giveaway.title} | Ganador: {winner_name}")


bot = AqiraxBot()


# --- ESTRUCTURA DE DATOS DEL GIVEAWAY ---
class Giveaway:
    def __init__(self, title, description, prize, host_id, channel_id, end_time, color=discord.Color.blurple(), thumbnail=None, image=None):
        self.title = title
        self.description = description
        self.prize = prize
        self.host_id = host_id
        self.channel_id = channel_id
        self.end_time = end_time
        self.color = color
        self.thumbnail = thumbnail
        self.image = image
        self.participants = set()  # IDs únicos
        self.finished = False
        self.message_id = None


# --- COMANDOS BÁSICOS (los mismos que antes) ---

@bot.tree.command(name="help", description="Muestra los comandos disponibles")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Comandos de Aqirax AI", color=discord.Color.blue())
    embed.add_field(name="/ban", value="Banea a un usuario.", inline=False)
    embed.add_field(name="/warn", value="Advierte a un usuario.", inline=False)
    embed.add_field(name="/kick", value="Expulsa a un usuario.", inline=False)
    embed.add_field(name="/user-info", value="Muestra información de un usuario.", inline=False)
    embed.add_field(name="/server-info", value="Muestra información del servidor.", inline=False)
    embed.add_field(name="/channel-info", value="Muestra información del canal.", inline=False)
    embed.add_field(name="/banner", value="Muestra el banner de un usuario.", inline=False)
    embed.add_field(name="/clearwarns", value="Limpia las advertencias de un usuario.", inline=False)
    embed.add_field(name="/send-embed", value="Abre el editor para crear un embed personalizado.", inline=False)
    embed.add_field(name="/giveaway", value="Crea un sorteo con UI interactiva.", inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


warns_db = {}


@bot.tree.command(name="ban", description="Banea a un usuario del servidor")
@app_commands.describe(member="Usuario a banear", reason="Razón del baneo")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "Sin razón especificada"):
    await member.ban(reason=reason)
    await interaction.response.send_message(f"🔨 {member.mention} ha sido baneado. Razón: {reason}", ephemeral=True)


@bot.tree.command(name="warn", description="Advierte a un usuario")
@app_commands.describe(member="Usuario a advertir", reason="Razón de la advertencia")
@app_commands.checks.has_permissions(manage_messages=True)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "Sin razón especificada"):
    user_id = member.id
    if user_id not in warns_db:
        warns_db[user_id] = []
    warns_db[user_id].append({
        "mod": interaction.user.id,
        "reason": reason,
        "date": datetime.datetime.now(datetime.timezone.utc)
    })
    await interaction.response.send_message(
        f"⚠️ {member.mention} ha sido advertido. Razón: {reason}\nTotal de warns: {len(warns_db[user_id])}",
        ephemeral=True
    )


@bot.tree.command(name="kick", description="Expulsa a un usuario del servidor")
@app_commands.describe(member="Usuario a expulsar", reason="Razón de la expulsión")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "Sin razón especificada"):
    await member.kick(reason=reason)
    await interaction.response.send_message(f"👢 {member.mention} ha sido expulsado. Razón: {reason}", ephemeral=True)


@bot.tree.command(name="user-info", description="Muestra información de un usuario")
@app_commands.describe(member="Usuario a consultar")
async def user_info(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"Información de {member.name}", color=member.color)
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="Nombre", value=member.mention, inline=True)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Creado", value=member.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Se unió", value=member.joined_at.strftime("%d/%m/%Y") if member.joined_at else "Desconocido", inline=True)
    embed.add_field(name="Roles", value=", ".join([r.mention for r in member.roles[1:]]) or "Ninguno", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="server-info", description="Muestra información del servidor")
async def server_info(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"Información de {guild.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.add_field(name="ID", value=guild.id, inline=True)
    embed.add_field(name="Dueño", value=guild.owner.mention if guild.owner else "Desconocido", inline=True)
    embed.add_field(name="Miembros", value=guild.member_count, inline=True)
    embed.add_field(name="Creado", value=guild.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Canales", value=len(guild.channels), inline=True)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="channel-info", description="Muestra información de un canal")
@app_commands.describe(channel="Canal a consultar")
async def channel_info(interaction: discord.Interaction, channel: discord.TextChannel = None):
    channel = channel or interaction.channel
    embed = discord.Embed(title=f"Información de {channel.name}", color=discord.Color.green())
    embed.add_field(name="Tipo", value=str(channel.type), inline=True)
    embed.add_field(name="ID", value=channel.id, inline=True)
    embed.add_field(name="Creado", value=channel.created_at.strftime("%d/%m/%Y"), inline=True)
    embed.add_field(name="Topic", value=channel.topic or "Sin tema", inline=False)
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="banner", description="Muestra el banner de un usuario")
@app_commands.describe(member="Usuario a consultar")
async def banner(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    try:
        user = await bot.fetch_user(member.id)
        if user.banner:
            embed = discord.Embed(title=f"Banner de {user.name}", color=discord.Color.purple())
            embed.set_image(url=user.banner.url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"{user.mention} no tiene banner configurado.", ephemeral=True)
    except Exception:
        await interaction.response.send_message("No se pudo obtener el banner.", ephemeral=True)


@bot.tree.command(name="clearwarns", description="Limpia las advertencias de un usuario")
@app_commands.describe(member="Usuario a limpiar")
@app_commands.checks.has_permissions(administrator=True)
async def clearwarns(interaction: discord.Interaction, member: discord.Member):
    if member.id in warns_db:
        warns_db[member.id] = []
        await interaction.response.send_message(f"✅ Las advertencias de {member.mention} han sido eliminadas.", ephemeral=True)
    else:
        await interaction.response.send_message(f"{member.mention} no tiene advertencias registradas.", ephemeral=True)


# --- SEND EMBED ---
class EmbedModal(discord.ui.Modal, title="Editor de Embed"):
    title_input = discord.ui.TextInput(label="Título", placeholder="Escribe el título del embed...", max_length=256, required=False)
    desc_input = discord.ui.TextInput(label="Descripción", placeholder="Escribe la descripción...", style=discord.TextStyle.paragraph, max_length=4096, required=False)
    color_input = discord.ui.TextInput(label="Color (Hex)", placeholder="Ejemplo: #5865F2", max_length=10, required=False, default="#5865F2")
    footer_input = discord.ui.TextInput(label="Pie de página", placeholder="Texto del footer...", max_length=2048, required=False)
    image_input = discord.ui.TextInput(label="URL de Imagen", placeholder="https://ejemplo.com/imagen.png", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        color_val = discord.Color.blue()
        if self.color_input.value:
            try:
                if self.color_input.value.startswith("#"):
                    color_val = discord.Color(int(self.color_input.value[1:], 16))
                else:
                    color_val = getattr(discord.Color, self.color_input.value.lower(), discord.Color.blue)()
            except Exception:
                pass

        embed = discord.Embed(
            title=self.title_input.value or None,
            description=self.desc_input.value or None,
            color=color_val,
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        if self.footer_input.value:
            embed.set_footer(text=self.footer_input.value)
        if self.image_input.value:
            embed.set_image(url=self.image_input.value)

        view = EmbedPreviewView(embed)
        await interaction.response.send_message(content="**Preview del Embed** (Solo tú lo ves):", embed=embed, view=view, ephemeral=True)


class EmbedPreviewView(discord.ui.View):
    def __init__(self, embed):
        super().__init__(timeout=300)
        self.embed = embed

    @discord.ui.button(label="Enviar", style=discord.ButtonStyle.green, emoji="✅")
    async def send_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.channel.send(embed=self.embed)
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="✅ **Embed enviado al canal.**", view=self)
        self.stop()

    @discord.ui.button(label="Seguir Editando", style=discord.ButtonStyle.blurple, emoji="✏️")
    async def edit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedModal())


@bot.tree.command(name="send-embed", description="Abre el editor para crear un embed personalizado")
async def send_embed(interaction: discord.Interaction):
    await interaction.response.send_modal(EmbedModal())


# ============================================================
#                    SISTEMA DE GIVEAWAY
# ============================================================

class GiveawayModal(discord.ui.Modal, title="Crear Sorteo"):
    titulo = discord.ui.TextInput(
        label="Título del sorteo",
        placeholder="Ej: Sorteo de Nitro",
        max_length=256,
        required=True
    )
    premio = discord.ui.TextInput(
        label="Premio",
        placeholder="Ej: 1 mes de Discord Nitro",
        max_length=256,
        required=True
    )
    descripcion = discord.ui.TextInput(
        label="Descripción",
        placeholder="Describe el sorteo...",
        style=discord.TextStyle.paragraph,
        max_length=1024,
        required=False
    )
    duracion = discord.ui.TextInput(
        label="Duración (en minutos)",
        placeholder="Ej: 60 (1 hora), 1440 (1 día)",
        max_length=6,
        required=True,
        default="60"
    )
    color = discord.ui.TextInput(
        label="Color del embed (Hex)",
        placeholder="Ej: #FF5733",
        max_length=10,
        required=False,
        default="#5865F2"
    )
    imagen = discord.ui.TextInput(
        label="URL de imagen (opcional)",
        placeholder="https://ejemplo.com/imagen.png",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Validar duración
        try:
            minutos = int(self.duracion.value)
            if minutos < 1 or minutos > 10080:  # máximo 7 días
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "❌ La duración debe ser un número entre 1 y 10080 minutos (7 días).",
                ephemeral=True
            )
            return

        # Procesar color
        color_val = discord.Color.blurple()
        if self.color.value:
            try:
                if self.color.value.startswith("#"):
                    color_val = discord.Color(int(self.color.value[1:], 16))
                else:
                    color_val = getattr(discord.Color, self.color.value.lower(), discord.Color.blurple)()
            except Exception:
                pass

        end_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=minutos)

        giveaway = Giveaway(
            title=self.titulo.value,
            description=self.descripcion.value or "¡Participa para ganar!",
            prize=self.premio.value,
            host_id=interaction.user.id,
            channel_id=interaction.channel.id,
            end_time=end_time,
            color=color_val,
            image=self.imagen.value or None
        )

        # Construir embed de preview
        embed = build_giveaway_embed(giveaway, interaction.user)
        view = GiveawayPreviewView(giveaway, embed)

        await interaction.response.send_message(
            content="👀 **Preview del Sorteo** (solo tú lo ves). Pulsa **Publicar** para enviarlo al canal.",
            embed=embed,
            view=view,
            ephemeral=True
        )


def build_giveaway_embed(giveaway: Giveaway, host: discord.abc.User) -> discord.Embed:
    """Construye el embed del sorteo con la información actual."""
    end_ts = int(giveaway.end_time.timestamp())
    embed = discord.Embed(
        title=f"🎉 {giveaway.title}",
        description=giveaway.description,
        color=giveaway.color
    )
    embed.add_field(name="🎁 Premio", value=giveaway.prize, inline=False)
    embed.add_field(name="👥 Participantes", value=f"`{len(giveaway.participants)}`", inline=True)
    embed.add_field(name="⏰ Termina", value=f"<t:{end_ts}:R>", inline=True)
    embed.add_field(name="🎯 Organizado por", value=host.mention, inline=False)
    if giveaway.image:
        embed.set_image(url=giveaway.image)
    embed.set_footer(text="Pulsa el botón para participar • Solo 1 vez por usuario")
    embed.timestamp = giveaway.end_time
    return embed


class GiveawayPreviewView(discord.ui.View):
    """Vista efímera que solo ve el creador, con botones Publicar/Cancelar/Editar."""
    def __init__(self, giveaway: Giveaway, embed: discord.Embed):
        super().__init__(timeout=600)
        self.giveaway = giveaway
        self.embed = embed

    @discord.ui.button(label="Publicar", style=discord.ButtonStyle.green, emoji="📢")
    async def publish(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Deshabilitar botones de la preview
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="✅ Publicando sorteo...",
            embed=self.embed,
            view=self
        )

        # Enviar el sorteo al canal
        view = GiveawayJoinView()
        message = await interaction.channel.send(embed=self.embed, view=view)

        # Guardar ID del mensaje en el giveaway
        self.giveaway.message_id = message.id
        bot.giveaways[message.id] = self.giveaway

        await interaction.followup.send(
            f"🎉 Sorteo publicado correctamente en {interaction.channel.mention}. Termina <t:{int(self.giveaway.end_time.timestamp())}:R>.",
            ephemeral=True
        )
        self.stop()

    @discord.ui.button(label="Editar", style=discord.ButtonStyle.blurple, emoji="✏️")
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GiveawayModal())

    @discord.ui.button(label="Cancelar", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(
            content="❌ Sorteo cancelado.",
            embed=None,
            view=self
        )
        self.stop()


class GiveawayJoinView(discord.ui.View):
    """Vista que se envía al canal con el botón de participar."""
    def __init__(self):
        super().__init__(timeout=None)  # Sin timeout, vive hasta que termine el sorteo

    @discord.ui.button(
        label="Participar",
        style=discord.ButtonStyle.success,
        emoji="🎉",
        custom_id="giveaway_join_button"
    )
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Buscar el giveaway por el ID del mensaje
        message_id = interaction.message.id
        giveaway = bot.giveaways.get(message_id)

        if giveaway is None:
            await interaction.response.send_message(
                "❌ Este sorteo ya no está activo o no se pudo encontrar.",
                ephemeral=True
            )
            return

        if giveaway.finished:
            await interaction.response.send_message(
                "❌ Este sorteo ya ha finalizado.",
                ephemeral=True
            )
            return

        # Verificar si ya participó
        if interaction.user.id in giveaway.participants:
            await interaction.response.send_message(
                "⚠️ Ya estás participando en este sorteo. Solo puedes hacerlo una vez.",
                ephemeral=True
            )
            return

        # Añadir participante
        giveaway.participants.add(interaction.user.id)

        # Actualizar el embed con el nuevo contador
        try:
            embed = interaction.message.embeds[0]
            # Buscar el campo de participantes y actualizarlo
            for i, field in enumerate(embed.fields):
                if field.name == "👥 Participantes":
                    embed.set_field_at(i, name="👥 Participantes", value=f"`{len(giveaway.participants)}`", inline=True)
                    break
            await interaction.message.edit(embed=embed)
        except Exception as e:
            print(f"⚠️ No se pudo actualizar el contador: {e}")

        await interaction.response.send_message(
            f"✅ ¡Estás participando en el sorteo **{giveaway.title}**! Mucha suerte 🍀",
            ephemeral=True
        )


@bot.tree.command(name="giveaway", description="Crea un sorteo con UI interactiva")
@app_commands.checks.has_permissions(manage_guild=True)
async def giveaway(interaction: discord.Interaction):
    await interaction.response.send_modal(GiveawayModal())


# --- SETUP MANUAL AUTOMOD ---
@bot.tree.command(name="setup-automod", description="Crea la regla de AutoMod en este servidor")
@app_commands.checks.has_permissions(administrator=True)
async def setup_automod_cmd(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    await bot.setup_automod(interaction.guild)
    await interaction.followup.send("Regla de AutoMod configurada (o ya existía).", ephemeral=True)


# Manejo de errores
@ban.error
@warn.error
@kick.error
@clearwarns.error
@setup_automod_cmd.error
@giveaway.error
async def permission_error(interaction: discord.Interaction, error):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("❌ No tienes permisos para usar este comando.", ephemeral=True)


if __name__ == "__main__":
    TOKEN = os.getenv("DISCORD_TOKEN")
    if not TOKEN:
        raise ValueError("❌ Falta la variable de entorno DISCORD_TOKEN")
    bot.run(TOKEN)
